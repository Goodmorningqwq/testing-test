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
    return {"status": "online", "version": "1.0.7-INTELLIGENCE"}

@router.get("/items", response_model=List[str])
async def get_items():
    query = "SELECT DISTINCT item_id FROM bazaar_prices WHERE timestamp >= NOW() - INTERVAL '24 hours' ORDER BY item_id;"
    if getattr(db, 'pool', None) is None: raise HTTPException(status_code=500, detail="DB disconnected")
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [row["item_id"] for row in rows]

@router.post("/optimize")
async def optimize_stream(request: OptimizeRequest):
    if request.budget <= 0: raise HTTPException(status_code=400, detail="Budget <= 0")
    async def event_generator():
        async for update in optimize_portfolio_stream(request.budget, request.horizon_days, request.candidate_items, request.mode, request.tax_rate):
            yield f"data: {json.dumps(update)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
