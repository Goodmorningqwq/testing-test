"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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
    setCurrentAction("Initializing Stream...");
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
            if (data.status === "starting") { setProgress(data.total === 0 ? 2 : 5); setCurrentAction(data.total === 0 ? "Fetching top items from DB..." : `Waking up ML models (${data.total} items)...`); }
            else if (data.status === "progress") { 
              setProgress(Math.floor((data.current / data.total) * 90) + 5); 
              setCurrentAction(`Analyzing ${data.item_id}... [${data.category}]`);
            }
            else if (data.status === "solving") { setProgress(98); setCurrentAction("Finding optimal allocation..."); }
            else if (data.status === "complete") { setProgress(100); setCurrentAction("Complete."); setResult(data.result); }
          }
        }
      }
    } catch (err: any) { setError("Failed to connect to backend engine."); }
    setLoading(false);
  };

  const formatNum = (val: any, d = 0) => {
    if (val === null || val === undefined || isNaN(val)) return "0";
    return Number(val).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: d });
  };

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-baseline">
           <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Portfolio Optimizer</h1>
           <span className="text-[10px] font-mono text-zinc-600">v1.0.6-STABLE</span>
        </div>
        <p className="text-zinc-400">Run the PuLP Linear Programming engine to find the exact optimal purchase allocations.</p>
      </div>
      {error && <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm font-mono tracking-tighter">⚠️ {error}</div>}
      <Card className="bg-zinc-900 border-zinc-800 max-w-xl">
        <CardContent className="space-y-6 pt-6">
          <div className="flex gap-4">
            <Input type="number" placeholder="Enter Coins..." value={budget} onChange={(e) => setBudget(e.target.value)} className="bg-zinc-800 border-zinc-700 text-zinc-100" />
            <Button disabled={loading} onClick={handleOptimize} className="bg-[#39FF14] text-black hover:bg-[#32e012] min-w-32">{loading ? "Crunching..." : "Run Engine"}</Button>
          </div>
          {loading && (
            <div className="space-y-2 animate-in fade-in">
              <div className="flex justify-between text-[10px] font-mono uppercase tracking-widest text-[#39FF14]"><span>{currentAction}</span><span>{progress}%</span></div>
              {/* Custom CSS Progress Bar */}
              <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-[#39FF14] transition-all duration-500 ease-out" 
                  style={{ width: `${progress}%` }} 
                />
              </div>
            </div>
          )}
          <div className="space-y-3">
             <div className="flex items-center space-x-4">
                <Button variant="outline" size="sm" className={`flex-1 h-10 ${investmentMode === 'lazy' ? 'bg-[#39FF14] text-black border-[#39FF14]' : 'text-zinc-400 border-zinc-700'}`} onClick={() => setInvestmentMode("lazy")}>Insta-Buy (Lazy)</Button>
                <Button variant="outline" size="sm" className={`flex-1 h-10 ${investmentMode === 'flipper' ? 'bg-[#f43f5e] text-white border-[#f43f5e]' : 'text-zinc-400 border-zinc-700'}`} onClick={() => setInvestmentMode("flipper")}>Buy Order (Flipper)</Button>
             </div>
          </div>
          <div className="space-y-3 border-t border-zinc-800 pt-4 flex items-center space-x-2">
             {[0.0125, 0.01, 0.05].map(v => (
                <Button key={v} variant="outline" size="sm" className={`flex-1 h-8 text-[10px] ${Math.abs(taxRate - v) < 0.0001 ? 'bg-zinc-100 text-black border-zinc-100' : 'text-zinc-500 border-zinc-700'}`} onClick={() => setTaxRate(v)}>{v === 0.05 ? "Derpy (5%)" : `${(v*100).toFixed(2)}% Tax`}</Button>
             ))}
          </div>
        </CardContent>
      </Card>
      {result && result.status === "optimal" && (
        <Card className="bg-zinc-900 border-zinc-800 overflow-hidden animate-in fade-in slide-in-from-bottom-4">
          <CardHeader className="border-b border-zinc-800 pb-6 mb-6">
             <div className="flex justify-between items-start">
                  <div>
                     <CardTitle className="text-zinc-100 font-vt323 text-2xl">Optimal Allocation Plan</CardTitle>
                     <p className="text-zinc-400 text-sm mt-1">Expected Net ROI: <span className="text-[#39FF14] font-bold">{(result.expected_portfolio_roi * 100).toFixed(2)}%</span></p>
                  </div>
                  <div className="text-right font-vt323 text-[#39FF14] text-xl">{formatNum(result.total_spent)} / {formatNum(result.budget_provided)}</div>
             </div>
             <div className="mt-4 p-3 bg-zinc-800/50 border border-zinc-700 rounded-lg text-[10px] text-zinc-400 font-mono uppercase tracking-tighter">
                🛡️ Bazaar Intelligence Active: Order Caps (71k/256/64) and 10% Depth Guard forced.
             </div>
          </CardHeader>
          <CardContent>
             <Table>
                <TableHeader><TableRow className="border-zinc-800">
                  <TableHead>Item ID</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="text-right">Game Max</TableHead>
                  <TableHead className="text-right">Total Cost</TableHead>
                  <TableHead className="text-[#39FF14] text-right">Net Profit</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {result.allocations?.map((alloc: any) => (
                    <TableRow key={alloc.item_id} className="border-zinc-800/50 hover:bg-zinc-800/20">
                      <TableCell><div className="font-bold text-zinc-100">{alloc.item_id}</div><div className="text-[10px] text-zinc-500 uppercase">{alloc.category}</div></TableCell>
                      <TableCell className="text-right text-zinc-100 font-mono">{formatNum(alloc.quantity)}</TableCell>
                      <TableCell className="text-right text-zinc-500 text-[10px] font-mono">LMT: {formatNum(alloc.game_limit_applied)}</TableCell>
                      <TableCell className="text-right text-zinc-400 font-mono">{formatNum(alloc.total_cost, 0)}</TableCell>
                      <TableCell className="text-right text-[#39FF14] font-bold text-lg font-vt323">+{formatNum(alloc.total_expected_profit, 0)}</TableCell>
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
