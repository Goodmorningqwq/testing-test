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

async def optimize_portfolio(budget: float, horizon_days: int, candidate_items: List[str] = None, mode: str = "lazy", tax_rate: float = 0.0125) -> Dict[str, Any]:
    if not candidate_items:
        candidate_items = await get_top_volume_items(limit=15)
        
    if not candidate_items:
        return {"error": "No items available to optimize."}

    logger.info(f"Optimizing budget {budget} over {len(candidate_items)} items for {horizon_days} days at {tax_rate*100}% tax.")
    
    net_predictions = []
    for item in candidate_items:
        pred = await generate_prediction(item, horizon_days=horizon_days)
        if pred and pred.get("current_price", 0) > 0:
            # Entry cost depends on mode
            cost = pred.get("current_buy_order_price", pred["current_price"]) if mode == "flipper" else pred["current_price"]
            
            # Predict the NET exit value after tax
            # Note: We apply calibration factor to the raw expected GAIN (or loss)
            raw_target_price = pred["predicted_end_price"]
            price_delta = raw_target_price - cost
            calibrated_exit_price = cost + (price_delta * pred.get("calibration_factor_applied", 1.0))
            
            # Final Net ROI calculation after tax
            # Tax is applied to the final sale price
            net_profit_per_unit = (calibrated_exit_price * (1 - tax_rate)) - cost
            net_roi = net_profit_per_unit / cost
            
            if net_roi > 0:
                # Inject net metrics for the solver to use
                pred["net_roi"] = net_roi
                pred["net_profit_per_unit"] = net_profit_per_unit
                net_predictions.append(pred)

    if not net_predictions:
        return {"error": f"No items found that are profitable after {tax_rate*100}% Bazaar tax."}

    # Integer Linear Programming using PuLP
    # Maximize SUM(x_i * net_profit_i)
    prob = pulp.LpProblem("SkyBlock_Portfolio_Optimization", pulp.LpMaximize)
    
    # Decision Variables
    item_vars = {}
    num_candidates = len(net_predictions)
    
    for p in net_predictions:
        item = p["item_id"]
        cost = p.get("current_buy_order_price", p["current_price"]) if mode == "flipper" else p["current_price"]
        
        # Max allocation: 40% of budget per asset to enforce diversification
        # VOLUME CONSTRAINT: 10% of the recorded market depth to prevent unrealistic orders
        market_depth = p["current_buy_volume"] if mode == "flipper" else p["current_sell_volume"]
        volume_cap = int(market_depth * 0.10)
        
        if num_candidates >= 3:
            max_qty = int((budget * 0.4) / cost)
        else:
            max_qty = int(budget / cost)
            
        max_qty_absolute = int(budget / cost)
        upper_bound = min(max_qty, max_qty_absolute, volume_cap if volume_cap > 0 else max_qty_absolute)
        
        if upper_bound > 0:
            item_vars[item] = pulp.LpVariable(f"qty_{item}", lowBound=0, upBound=upper_bound, cat='Integer')
        elif num_candidates < 3 and max_qty_absolute >= 1 and volume_cap >= 1:
            # Fallback: if we have very few items, at least allow buying one if budget and volume permits
            item_vars[item] = pulp.LpVariable(f"qty_{item}", lowBound=0, upBound=1, cat='Integer')

    if not item_vars:
        return {"error": "Budget too low or liquidity too thin to purchase profitable items."}

    profits_expr = []
    costs_expr = []
    
    for p in net_predictions:
        item = p["item_id"]
        if item in item_vars:
            cost = p.get("current_buy_order_price", p["current_price"]) if mode == "flipper" else p["current_price"]
            net_profit = p["net_profit_per_unit"]
            profits_expr.append(item_vars[item] * net_profit)
            costs_expr.append(item_vars[item] * cost)
            
    # Objective: Maximize Total Net Profit
    prob += pulp.lpSum(profits_expr), "Total_Expected_Net_Profit"
    
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
    total_expected_net_profit = 0
    
    for p in net_predictions:
        item = p["item_id"]
        if item in item_vars:
            qty = int(item_vars[item].varValue)
            if qty > 0:
                cost = p.get("current_buy_order_price", p["current_price"]) if mode == "flipper" else p["current_price"]
                market_depth = p["current_buy_volume"] if mode == "flipper" else p["current_sell_volume"]
                net_profit = p["net_profit_per_unit"]
                allocations.append({
                    "item_id": item,
                    "quantity": qty,
                    "unit_price": cost,
                    "total_cost": qty * cost,
                    "market_volume": market_depth,
                    "volume_cap_applied": int(market_depth * 0.10),
                    "expected_profit_per_unit": net_profit,
                    "total_expected_profit": qty * net_profit,
                    "roi": p["net_roi"],
                    "tax_applied": tax_rate
                })
                total_spent += (qty * cost)
                total_expected_net_profit += (qty * net_profit)
                
    allocations.sort(key=lambda x: x["total_expected_profit"], reverse=True)
    
    return {
        "status": "optimal",
        "budget_provided": budget,
        "tax_rate": tax_rate,
        "total_spent": total_spent,
        "remaining_budget": budget - total_spent,
        "total_expected_profit": total_expected_net_profit,
        "expected_portfolio_roi": (total_expected_net_profit / total_spent) if total_spent > 0 else 0,
        "allocations": allocations
    }
