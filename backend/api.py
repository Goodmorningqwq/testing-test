import json
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from db import db
from predictor import generate_prediction
from optimizer import optimize_portfolio_stream

class OptimizeRequest(BaseModel):
    budget: float
    horizon_days: int = 7
    candidate_items: List[str] = []
    mode: str = "lazy"
    tax_rate: float = 0.0125

router = APIRouter(prefix="/api")

@router.get("/health")
async def health():
    return {"status": "online", "version": "1.0.9-ADAPTIVE"}

@router.get("/items", response_model=List[str])
async def get_items():
    query = "SELECT DISTINCT item_id FROM bazaar_prices WHERE timestamp >= NOW() - INTERVAL '24 hours' ORDER BY item_id;"
    if getattr(db, 'pool', None) is None: raise HTTPException(status_code=500, detail="DB disconnected")
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [row["item_id"] for row in rows]

@router.get("/history/{item_id}")
async def get_history(item_id: str, days: int = Query(default=1, ge=1, le=30)):
    """Return raw OHLC-style price history for the dashboard chart."""
    if getattr(db, 'pool', None) is None:
        raise HTTPException(status_code=500, detail="DB disconnected")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = """
        SELECT timestamp, buy_price, sell_price, buy_volume, sell_volume
        FROM bazaar_prices
        WHERE item_id = $1 AND timestamp >= $2
        ORDER BY timestamp ASC;
    """
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query, item_id.upper(), cutoff)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data found for {item_id} in the last {days} day(s).")
    return [dict(r) for r in rows]

@router.get("/predict/{item_id}")
async def predict_item(item_id: str, horizon_days: int = Query(default=7, ge=1, le=30)):
    """Run the Prophet ML model for a given item and return the prediction."""
    if getattr(db, 'pool', None) is None:
        raise HTTPException(status_code=500, detail="DB disconnected")
    result = await generate_prediction(item_id.upper(), horizon_days=horizon_days)
    if not result:
        raise HTTPException(status_code=400, detail=f"Insufficient data to generate prediction for {item_id}. Need at least 10 data points.")
    return result

@router.post("/optimize")
async def optimize_stream(request: OptimizeRequest):
    if request.budget <= 0: raise HTTPException(status_code=400, detail="Budget <= 0")
    async def event_generator():
        async for update in optimize_portfolio_stream(request.budget, request.horizon_days, request.candidate_items, request.mode, request.tax_rate):
            yield f"data: {json.dumps(update)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
