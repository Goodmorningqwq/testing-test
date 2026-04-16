import os

OPTIMIZER_CODE = r"""import pulp
import logging
import math
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from db import db
from predictor import generate_prediction

logger = logging.getLogger("optimizer")

# --- BAZAAR INTELLIGENCE KEYWORDS ---
COMMODITY_KEYWORDS = [
    "ENCHANTED_", "_FRAGMENT", "_ORE", "_INGOT", "_LOG", "SEEDS", "WHEAT", 
    "CARROT", "POTATO", "PUMPKIN", "MELON", "SUGAR_CANE", "MUSHROOM", 
    "CACTUS", "LEATHER", "FEATHER", "PORK", "CHICKEN", "MUTTON", "BEEF", 
    "SLIME", "MAGMA", "BLAZE", "ENDER", "EYE", "BONE", "ROTTEN", "SULPHUR", 
    "POWDER", "FLINT", "GRAVEL", "SAND", "ICE", "SNOW", "CLAY", "QUARTZ", 
    "GLOWSTONE", "_STONE", "_SHARD", "_ESSENCE", "_DUST", "STOCK_OF_STONKS"
]
SPECIALIZED_KEYWORDS = ["RECOMBOBULATOR", "ULTIMATE_", "TRAVEL_SCROLL", "_UPGRADE", "_GENERATOR", "FUMING_POTATO_BOOK"]
ULTRA_LIMITED_KEYWORDS = ["BOOSTER_COOKIE", "GOD_POTION", "_PET_ITEM"]

def get_item_max_order_size(item_id: str) -> int:
    item_id = item_id.upper()
    if any(k in item_id for k in ULTRA_LIMITED_KEYWORDS): return 64
    if any(k in item_id for k in SPECIALIZED_KEYWORDS): return 256
    if any(k in item_id for k in COMMODITY_KEYWORDS): return 71680
    return 71680

def get_item_category_label(item_id: str) -> str:
    item_id = item_id.upper()
    if any(k in item_id for k in ULTRA_LIMITED_KEYWORDS): return "Ultra-Limited"
    if any(k in item_id for k in SPECIALIZED_KEYWORDS): return "Specialized"
    if any(k in item_id for k in COMMODITY_KEYWORDS): return "Commodity"
    return "Unknown (Default Cap)"

def safe_float(val: Any) -> float:
    try:
        f = float(val)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except: return 0.0

async def get_top_volume_items(limit: int = 15) -> List[str]:
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT item_id FROM bazaar_prices WHERE timestamp >= NOW() - INTERVAL '2 hours' GROUP BY item_id ORDER BY SUM(buy_volume + sell_volume) DESC LIMIT $1;", limit)
    return [row["item_id"] for row in rows]

async def optimize_portfolio_stream(budget: float, horizon_days: int, candidate_items: List[str] = None, mode: str = "lazy", tax_rate: float = 0.0125) -> AsyncGenerator[Dict[str, Any], None]:
    budget = safe_float(budget)
    if not candidate_items: candidate_items = await get_top_volume_items(limit=15)
    if not candidate_items: yield {"error": "No items found."}; return
    yield {"status": "starting", "total": len(candidate_items), "ver": "1.0.7"}
    net_predictions = []
    for i, item in enumerate(candidate_items):
        yield {"status": "progress", "current": i + 1, "total": len(candidate_items), "item_id": item, "category": get_item_category_label(item)}
        pred = await generate_prediction(item, horizon_days=horizon_days)
        if pred and safe_float(pred.get("current_price", 0)) > 0:
            cost = safe_float(pred.get("current_buy_order_price", pred["current_price"])) if mode == "flipper" else safe_float(pred["current_price"])
            if cost <= 0: continue
            depth = safe_float(pred.get("current_buy_volume" if mode == "flipper" else "current_sell_volume", 0))
            if depth <= 0: continue
            
            # FIXED LOGIC
            raw_target = safe_float(pred.get("predicted_end_price", 0))
            net_p = (raw_target * (1 - tax_rate)) - cost
            net_roi = net_p / cost
            if net_roi > 0:
                pred["net_profit_per_unit"] = net_p
                pred["net_roi"] = net_roi
                net_predictions.append(pred)
    
    if not net_predictions: yield {"error": "No profitable items."}; return
    yield {"status": "solving"}
    prob = pulp.LpProblem("SkyBlock_Optimizer", pulp.LpMaximize)
    item_vars = {}
    for p in net_predictions:
        item = p["item_id"]
        cost = safe_float(p.get("current_buy_order_price", p["current_price"])) if mode == "flipper" else safe_float(p["current_price"])
        depth = safe_float(p.get("current_buy_volume" if mode == "flipper" else "current_sell_volume", 0))
        # STRICT CAPS
        limit_val = min(int(depth * 0.10), get_item_max_order_size(item), int((budget * 0.4) / cost) if len(net_predictions) >= 3 else int(budget / cost))
        if limit_val > 0: item_vars[item] = pulp.LpVariable(f"qty_{item}", lowBound=0, upBound=limit_val, cat='Integer')

    if not item_vars: yield {"error": "Liquidity too low."}; return
    prob += pulp.lpSum([item_vars[p["item_id"]] * p["net_profit_per_unit"] for p in net_predictions if p["item_id"] in item_vars])
    prob += pulp.lpSum([item_vars[p["item_id"]] * (safe_float(p.get("current_buy_order_price", p["current_price"])) if mode == "flipper" else safe_float(p["current_price"])) for p in net_predictions if p["item_id"] in item_vars]) <= budget
    await asyncio.get_event_loop().run_in_executor(None, prob.solve, pulp.PULP_CBC_CMD(msg=0))
    
    allocs = []
    total_spent = 0
    total_profit = 0
    for p in net_predictions:
        item = p["item_id"]
        if item in item_vars:
            qty = int(item_vars[item].varValue)
            if qty > 0:
                cost = safe_float(p.get("current_buy_order_price", p["current_price"])) if mode == "flipper" else safe_float(p["current_price"])
                p_unit = p["net_profit_per_unit"]
                allocs.append({
                    "item_id": item, "quantity": qty, "unit_price": cost, "total_cost": float(qty * cost),
                    "game_limit_applied": get_item_max_order_size(item), "category": get_item_category_label(item),
                    "total_expected_profit": float(qty * p_unit), "roi": float(p["net_roi"])
                })
                total_spent += qty * cost
                total_profit += qty * p_unit
    yield {"status": "complete", "result": {
        "status": "optimal", "budget_provided": float(budget), "tax_rate": float(tax_rate), "total_spent": float(total_spent),
        "total_expected_profit": float(total_profit), "expected_portfolio_roi": float(total_profit / total_spent) if total_spent > 0 else 0, "allocations": allocs
    }}
"""

API_CODE = r'''import json
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
'''

def write_repair():
    print("Repairing backend/optimizer.py (v1.0.7)...")
    with open("backend/optimizer.py", "w", encoding="utf-8") as f:
        f.write(OPTIMIZER_CODE)
    
    print("Repairing backend/api.py (v1.0.7)...")
    with open("backend/api.py", "w", encoding="utf-8") as f:
        f.write(API_CODE)
    
if __name__ == "__main__":
    write_repair()
