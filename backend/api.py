from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from db import db
from predictor import generate_prediction
from optimizer import optimize_portfolio

class OptimizeRequest(BaseModel):
    budget: float
    horizon_days: int = 7
    candidate_items: List[str] = []
    mode: str = "lazy"

class LogRequest(BaseModel):
    plan_id: str
    recommended_items: str
    budget: float
    horizon_days: int
    predicted_roi: float
    actual_roi: float
    actual_profit: float
    notes: str = ""

router = APIRouter(prefix="/api")

@router.get("/items", response_model=List[str])
async def get_items():
    """Retrieve a list of all distinct tracking items from recent history."""
    # We restrict to last 1 hour to prevent full table scans and keep query ultra-fast
    query = """
        SELECT DISTINCT item_id 
        FROM bazaar_prices 
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY item_id;
    """
    
    if getattr(db, 'pool', None) is None:
         raise HTTPException(status_code=500, detail="Database connection not available")
        
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    
    return [row["item_id"] for row in rows]

@router.get("/history/{item_id}", response_model=List[Dict[str, Any]])
async def get_history(item_id: str, days: int = Query(30, description="Days of history to retrieve")):
    """Get historical data for a specific item_id over a given number of days."""
    if getattr(db, 'pool', None) is None:
         raise HTTPException(status_code=500, detail="Database connection not available")
        
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = """
        SELECT timestamp, buy_price, buy_volume, sell_price, sell_volume 
        FROM bazaar_prices 
        WHERE item_id = $1 AND timestamp >= $2 
        ORDER BY timestamp ASC;
    """
    
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query, item_id, cutoff_time)
        
    if not rows:
        raise HTTPException(status_code=404, detail="No historical data found for this item.")
        
    # asyncpg records to dicts
    return [dict(row) for row in rows]


@router.get("/predict/{item_id}")
async def get_prediction(item_id: str, days_history: int = Query(30, description="History points to feed"), horizon_days: int = Query(7, description="Days ahead to predict")):
    """Generate or retrieve a cached Prophet prediction for an item."""
    prediction = await generate_prediction(item_id, days_history, horizon_days)
    if not prediction:
        raise HTTPException(status_code=400, detail="Not enough data to generate prediction, or model failed.")
    return prediction

@router.post("/optimize")
async def optimize(request: OptimizeRequest):
    """Run PuLP optimizer against prophet predictions for optimal budget allocation."""
    if request.budget <= 0:
        raise HTTPException(status_code=400, detail="Budget must be greater than zero.")
        
    result = await optimize_portfolio(request.budget, request.horizon_days, request.candidate_items, request.mode)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
    return result

@router.post("/logs")
async def add_log(log: LogRequest):
    if getattr(db, 'pool', None) is None:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    query = """
    INSERT INTO user_investment_logs 
    (plan_id, recommended_items, budget, horizon_days, predicted_roi, actual_roi, actual_profit, notes)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    RETURNING id;
    """
    async with db.pool.acquire() as conn:
        new_id = await conn.fetchval(query, log.plan_id, log.recommended_items, log.budget, log.horizon_days, log.predicted_roi, log.actual_roi, log.actual_profit, log.notes)
    return {"status": "success", "id": new_id}

@router.get("/logs")
async def get_logs():
    if getattr(db, 'pool', None) is None:
        raise HTTPException(status_code=500, detail="Database connection not available")
        
    query = "SELECT * FROM user_investment_logs ORDER BY timestamp DESC LIMIT 50;"
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [dict(row) for row in rows]

