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
    yield {"status": "starting", "total": len(candidate_items)}
    net_predictions = []
    for i, item in enumerate(candidate_items):
        yield {"status": "progress", "current": i + 1, "total": len(candidate_items), "item_id": item, "category": get_item_category_label(item)}
        pred = await generate_prediction(item, horizon_days=horizon_days)
        if pred and safe_float(pred.get("current_price", 0)) > 0:
            cost = safe_float(pred.get("current_buy_order_price", pred["current_price"])) if mode == "flipper" else safe_float(pred["current_price"])
            if cost <= 0: continue
            depth = safe_float(pred.get("current_buy_volume" if mode == "flipper" else "current_sell_volume", 0))
            if depth <= 0: continue
            roi = ((safe_float(p.get("predicted_end_price", 0)) * (1 - tax_rate)) - cost) / cost if 'p' in locals() else 0 # Fix: pred instead of p
            # Correcting the ROI logic in the template
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
        limit = min(int(depth * 0.10), get_item_max_order_size(item), int((budget * 0.4) / cost) if len(net_predictions) >= 3 else int(budget / cost))
        if limit > 0: item_vars[item] = pulp.LpVariable(f"qty_{item}", lowBound=0, upBound=limit, cat='Integer')
    if not item_vars: yield {"error": "Liquidity too low."}; return
    prob += pulp.lpSum([item_vars[p["item_id"]] * p["net_profit_per_unit"] for p in net_predictions if p["item_id"] in item_vars])
    prob += pulp.lpSum([item_vars[p["item_id"]] * (safe_float(p.get("current_buy_order_price", p["current_price"])) if mode == "flipper" else safe_float(p["current_price"])) for p in net_predictions if p["item_id"] in item_vars]) <= budget
    await asyncio.get_event_loop().run_in_executor(None, prob.solve, pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != 'Optimal': yield {"error": "Infeasible."}; return
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
                    "item_id": item, "quantity": qty, "unit_price": cost, "total_cost": qty * cost,
                    "game_limit_applied": get_item_max_order_size(item), "category": get_item_category_label(item),
                    "total_expected_profit": qty * p_unit, "roi": p["net_roi"]
                })
                total_spent += qty * cost
                total_profit += qty * p_unit
    yield {"status": "complete", "result": {
        "status": "optimal", "budget_provided": budget, "tax_rate": tax_rate, "total_spent": total_spent,
        "total_expected_profit": total_profit, "expected_portfolio_roi": total_profit / total_spent if total_spent > 0 else 0, "allocations": allocs
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
    query = "SELECT DISTINCT item_id FROM bazaar_prices WHERE timestamp >= NOW() - INTERVAL '24 hours' ORDER BY item_id;"
    if getattr(db, 'pool', None) is None: raise HTTPException(status_code=500, detail="DB disconnected")
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [row["item_id"] for row in rows]

@router.get("/history/{item_id}", response_model=List[Dict[str, Any]])
async def get_history(item_id: str, days: int = Query(30)):
    if getattr(db, 'pool', None) is None: raise HTTPException(status_code=500, detail="DB disconnected")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = "SELECT timestamp, buy_price, buy_volume, sell_price, sell_volume FROM bazaar_prices WHERE item_id = $1 AND timestamp >= $2 ORDER BY timestamp ASC;"
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query, item_id, cutoff)
    return [dict(row) for row in rows]

@router.get("/predict/{item_id}")
async def get_prediction(item_id: str, days_history: int = Query(30), horizon_days: int = Query(7)):
    prediction = await generate_prediction(item_id, days_history, horizon_days)
    if not prediction: raise HTTPException(status_code=400, detail="Model failed")
    return prediction

@router.post("/optimize")
async def optimize_stream(request: OptimizeRequest):
    if request.budget <= 0: raise HTTPException(status_code=400, detail="Budget <= 0")
    async def event_generator():
        async for update in optimize_portfolio_stream(request.budget, request.horizon_days, request.candidate_items, request.mode, request.tax_rate):
            yield f"data: {json.dumps(update)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/logs")
async def add_log(log: LogRequest):
    if getattr(db, 'pool', None) is None: raise HTTPException(status_code=500, detail="DB disconnected")
    query = "INSERT INTO user_investment_logs (plan_id, recommended_items, budget, horizon_days, predicted_roi, actual_roi, actual_profit, notes) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id;"
    async with db.pool.acquire() as conn:
        new_id = await conn.fetchval(query, log.plan_id, log.recommended_items, log.budget, log.horizon_days, log.predicted_roi, log.actual_roi, log.actual_profit, log.notes)
    return {"status": "success", "id": new_id}

@router.get("/logs")
async def get_logs():
    if getattr(db, 'pool', None) is None: raise HTTPException(status_code=500, detail="DB disconnected")
    query = "SELECT * FROM user_investment_logs ORDER BY timestamp DESC LIMIT 50;"
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [dict(row) for row in rows]
'''

PAGE_CODE = r'''"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Planner() {
  const [budget, setBudget] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [investmentMode, setInvestmentMode] = useState("lazy");
  const [taxRate, setTaxRate] = useState(0.0125);
  const [error, setError] = useState<string | null>(null);

  const [progress, setProgress] = useState(0);
  const [currentAction, setCurrentAction] = useState("");

  const handleOptimize = async () => {
    const parsedBudget = parseFloat(budget);
    if (!budget || isNaN(parsedBudget) || parsedBudget <= 0) {
      setError("Please enter a valid budget."); return;
    }
    setLoading(true); setResult(null); setError(null); setProgress(0);
    setCurrentAction("Initializing...");
    try {
      const resp = await fetch(`${API_BASE_URL}/api/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget: parsedBudget, horizon_days: 7, candidate_items: [], mode: investmentMode, tax_rate: taxRate })
      });
      if (!resp.ok) throw new Error("Server error");
      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No reader");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.substring(6));
            if (data.error) { setError(data.error); setLoading(false); return; }
            if (data.status === "starting") { setProgress(5); setCurrentAction("Starting calculation..."); }
            else if (data.status === "progress") { 
              setProgress(Math.floor((data.current / data.total) * 90) + 5); 
              setCurrentAction(`Predicting ${data.item_id}... [${data.category}]`);
            }
            else if (data.status === "solving") { setProgress(98); setCurrentAction("Solving optimization..."); }
            else if (data.status === "complete") { setProgress(100); setCurrentAction("Done."); setResult(data.result); }
          }
        }
      }
    } catch (err: any) { setError("Failed to connect to backend."); }
    setLoading(false);
  };

  const formatNum = (val: any, d = 0) => {
    if (val === null || val === undefined || isNaN(val)) return "0";
    return Number(val).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: d });
  };

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Portfolio Optimizer</h1>
        <p className="text-zinc-400">Run the PuLP Linear Programming engine to find the exact optimal purchase allocations.</p>
      </div>
      {error && <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm font-mono tracking-tighter">⚠️ {error}</div>}
      <Card className="bg-zinc-900 border-zinc-800 max-w-xl">
        <CardContent className="space-y-6 pt-6">
          <div className="flex gap-4">
            <Input type="number" placeholder="Coins..." value={budget} onChange={(e) => setBudget(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-100" />
            <Button disabled={loading} onClick={handleOptimize} className="bg-[#39FF14] text-black hover:bg-[#32e012] min-w-32">{loading ? "Running..." : "Run Engine"}</Button>
          </div>
          {loading && (
            <div className="space-y-2">
              <div className="flex justify-between text-[10px] font-mono uppercase tracking-widest text-[#39FF14]"><span>{currentAction}</span><span>{progress}%</span></div>
              <Progress value={progress} className="h-1.5 bg-zinc-800" />
            </div>
          )}
          <div className="space-y-3">
             <div className="flex items-center space-x-4">
                <Button variant="outline" size="sm" className={`flex-1 h-10 ${investmentMode === 'lazy' ? 'bg-[#39FF14] text-black' : 'text-zinc-400'}`} onClick={() => setInvestmentMode("lazy")}>Lazy Investor</Button>
                <Button variant="outline" size="sm" className={`flex-1 h-10 ${investmentMode === 'flipper' ? 'bg-[#f43f5e] text-white' : 'text-zinc-400'}`} onClick={() => setInvestmentMode("flipper")}>Margin Flipper</Button>
             </div>
          </div>
          <div className="space-y-3 border-t border-zinc-800 pt-4 flex items-center space-x-2">
             {[0.0125, 0.01, 0.05].map(v => (
                <Button key={v} variant="outline" size="sm" className={`flex-1 h-8 text-[10px] ${Math.abs(taxRate - v) < 0.0001 ? 'bg-zinc-100 text-black' : 'text-zinc-500'}`} onClick={() => setTaxRate(v)}>{v === 0.05 ? "Derpy (5%)" : `${(v*100).toFixed(2)}%`}</Button>
             ))}
          </div>
        </CardContent>
      </Card>
      {result && result.status === "optimal" && (
        <Card className="bg-zinc-900 border-zinc-800 overflow-hidden">
          <CardHeader className="border-b border-zinc-800 pb-6 mb-6">
             <div className="flex justify-between items-start">
                  <div>
                     <CardTitle className="text-zinc-100 font-vt323 text-2xl">Optimal Allocation Plan</CardTitle>
                     <p className="text-zinc-400 text-sm mt-1">Expected Net ROI: <span className="text-[#39FF14] font-bold">{(result.expected_portfolio_roi * 100).toFixed(2)}%</span></p>
                  </div>
                  <div className="text-right font-vt323 text-[#39FF14] text-xl">{formatNum(result.total_spent)} / {formatNum(result.budget_provided)}</div>
             </div>
             <div className="mt-4 p-3 bg-zinc-800/50 border border-zinc-700 rounded-lg text-[10px] text-zinc-400 font-mono uppercase tracking-tighter">
                🛡️ Bazaar Intelligence: Physical caps (71k/256/64) and 10% depth guard active.
             </div>
          </CardHeader>
          <CardContent>
             <Table>
                <TableHeader><TableRow className="border-zinc-800">
                  <TableHead>Item</TableHead>
                  <TableHead className="text-right">Qty</TableHead>
                  <TableHead className="text-right">Game Max</TableHead>
                  <TableHead className="text-right">Total Cost</TableHead>
                  <TableHead className="text-[#39FF14] text-right">Net Profit</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {result.allocations?.map((alloc: any) => (
                    <TableRow key={alloc.item_id} className="border-zinc-800/50">
                      <TableCell><div className="font-bold text-zinc-100">{alloc.item_id}</div><div className="text-[10px] text-zinc-500 uppercase">{alloc.category}</div></TableCell>
                      <TableCell className="text-right text-zinc-100 font-mono">{formatNum(alloc.quantity)}</TableCell>
                      <TableCell className="text-right text-zinc-500 text-[10px] font-mono">Limit: {formatNum(alloc.game_limit_applied)}</TableCell>
                      <TableCell className="text-right text-zinc-400 font-mono">{formatNum(alloc.total_cost, 1)}</TableCell>
                      <TableCell className="text-right text-[#39FF14] font-bold text-lg font-vt323">+{formatNum(alloc.total_expected_profit, 1)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
             </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
'''

def write_repair():
    print("Repairing backend/optimizer.py...")
    with open("backend/optimizer.py", "w", encoding="utf-8") as f:
        f.write(OPTIMIZER_CODE)
    
    print("Repairing backend/api.py...")
    with open("backend/api.py", "w", encoding="utf-8") as f:
        f.write(API_CODE)

    print("Repairing frontend/src/app/planner/page.tsx...")
    with open("frontend/src/app/planner/page.tsx", "w", encoding="utf-8") as f:
        f.write(PAGE_CODE)
    
    print("Verification...")
    print(f"Optimizer Size: {os.path.getsize('backend/optimizer.py')} bytes")
    print(f"API Size: {os.path.getsize('backend/api.py')} bytes")
    print(f"Page Size: {os.path.getsize('frontend/src/app/planner/page.tsx')} bytes")
    
if __name__ == "__main__":
    write_repair()
