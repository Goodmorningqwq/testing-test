import pulp
import logging
from typing import List, Dict, Any
from db import db
from predictor import generate_prediction

logger = logging.getLogger("optimizer")

async def get_top_volume_items(limit: int = 15) -> List[str]:
    """Fallback: Fetch the most liquid items from the last 2 hours to optimize over."""
    if getattr(db, 'pool', None) is None:
        return []
    
    query = """
        SELECT item_id, SUM(buy_volume + sell_volume) as total_volume
        FROM bazaar_prices
        WHERE timestamp >= NOW() - INTERVAL '2 hours'
        GROUP BY item_id
        ORDER BY total_volume DESC
        LIMIT $1;
    """
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query, limit)
    
    return [row["item_id"] for row in rows]

async def optimize_portfolio(budget: float, horizon_days: int, candidate_items: List[str] = None, mode: str = "lazy") -> Dict[str, Any]:
    if not candidate_items:
        candidate_items = await get_top_volume_items(limit=15)
        
    if not candidate_items:
        return {"error": "No items available to optimize."}

    logger.info(f"Optimizing budget {budget} over {len(candidate_items)} items for {horizon_days} days.")
    
    predictions = []
    for item in candidate_items:
        pred = await generate_prediction(item, horizon_days=horizon_days)
        # Only invest in items expected to grow
        roi_key = "flipper_calibrated_roi" if mode == "flipper" else "calibrated_roi"
        if pred and pred.get(roi_key, 0) > 0 and pred.get("current_price", 0) > 0:
            predictions.append(pred)

    if not predictions:
        return {"error": "No profitable items found to invest in based on current predictions."}

    # Integer Linear Programming using PuLP
    # Maximize SUM(x_i * profit_i)
    # Subject to SUM(x_i * cost_i) <= budget
    
    prob = pulp.LpProblem("SkyBlock_Portfolio_Optimization", pulp.LpMaximize)
    
    # Decision Variables
    item_vars = {}
    for p in predictions:
        item = p["item_id"]
        cost = p.get("current_buy_order_price", p["current_price"]) if mode == "flipper" else p["current_price"]
        roi = p.get("flipper_calibrated_roi", p["calibrated_roi"]) if mode == "flipper" else p["calibrated_roi"]
        profit = cost * roi
        
        # Max allocation: 40% of budget per asset to enforce diversification
        max_qty_for_diversification = int((budget * 0.4) / cost)
        max_qty_absolute = int(budget / cost)
        
        # If budget is tiny, allow at least 1 unit if they can afford it
        upper_bound = max(max_qty_for_diversification, 1) if max_qty_absolute > 0 else 0
        upper_bound = min(upper_bound, max_qty_absolute)
        
        if upper_bound > 0:
            item_vars[item] = pulp.LpVariable(f"qty_{item}", lowBound=0, upBound=upper_bound, cat='Integer')

    if not item_vars:
        return {"error": "Budget too low to purchase any profitable items."}

    profits_expr = []
    costs_expr = []
    
    for p in predictions:
        item = p["item_id"]
        if item in item_vars:
            cost = p.get("current_buy_order_price", p["current_price"]) if mode == "flipper" else p["current_price"]
            roi = p.get("flipper_calibrated_roi", p["calibrated_roi"]) if mode == "flipper" else p["calibrated_roi"]
            profit = cost * roi
            profits_expr.append(item_vars[item] * profit)
            costs_expr.append(item_vars[item] * cost)
            
    # Objective
    prob += pulp.lpSum(profits_expr), "Total_Expected_Profit"
    
    # Constraint
    prob += pulp.lpSum(costs_expr) <= budget, "Total_Cost"
    
    # Solve
    try:
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
    except Exception as e:
        logger.error(f"Solver Error: {e}")
        return {"error": "Optimization solver failed."}
        
    if pulp.LpStatus[prob.status] != 'Optimal':
        return {"error": f"Could not find optimal solution. Status: {pulp.LpStatus[prob.status]}"}

    # Extract allocations
    allocations = []
    total_spent = 0
    total_expected_profit = 0
    
    for p in predictions:
        item = p["item_id"]
        if item in item_vars:
            qty = int(item_vars[item].varValue)
            if qty > 0:
                cost = p.get("current_buy_order_price", p["current_price"]) if mode == "flipper" else p["current_price"]
                roi = p.get("flipper_calibrated_roi", p["calibrated_roi"]) if mode == "flipper" else p["calibrated_roi"]
                profit = cost * roi
                allocations.append({
                    "item_id": item,
                    "quantity": qty,
                    "unit_price": cost,
                    "total_cost": qty * cost,
                    "expected_profit_per_unit": profit,
                    "total_expected_profit": qty * profit,
                    "roi": roi
                })
                total_spent += (qty * cost)
                total_expected_profit += (qty * profit)
                
    allocations.sort(key=lambda x: x["total_expected_profit"], reverse=True)
    
    return {
        "status": "optimal",
        "budget_provided": budget,
        "total_spent": total_spent,
        "remaining_budget": budget - total_spent,
        "total_expected_profit": total_expected_profit,
        "expected_portfolio_roi": (total_expected_profit / total_spent) if total_spent > 0 else 0,
        "allocations": allocations
    }
