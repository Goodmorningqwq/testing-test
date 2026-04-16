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

  const handleOptimize = async () => {
    const parsedBudget = parseFloat(budget);
    if (!budget || isNaN(parsedBudget) || parsedBudget <= 0) {
      setError("Please enter a valid positive budget amount.");
      return;
    }

    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          budget: parsedBudget, 
          horizon_days: 7, 
          candidate_items: [], 
          mode: investmentMode,
          tax_rate: taxRate 
        })
      });
      const data = await res.json();
      if (!res.ok) {
         const msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
         setError(msg || "Optimization engine rejected the request.");
      } else {
         setResult(data);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message === "Failed to fetch" ? "Backend connection lost or waking up..." : "Failed to connect to optimization engine.");
    }
    setLoading(false);
  };

  // Safety formatter for numbers
  const formatNum = (val: any, decimals = 0) => {
    if (val === null || val === undefined || isNaN(val)) return "0";
    return Number(val).toLocaleString(undefined, { 
      minimumFractionDigits: 0, 
      maximumFractionDigits: decimals 
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Portfolio Optimizer</h1>
        <p className="text-zinc-400">Run the PuLP Linear Programming engine to find the exact optimal purchase allocations.</p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm font-mono animate-in fade-in slide-in-from-top-2">
           <span className="font-bold mr-2">⚠️ ERROR:</span> {error}
        </div>
      )}

      <Card className="bg-zinc-900 border-zinc-800 max-w-xl">
        <CardHeader>
          <CardTitle className="text-zinc-100 font-vt323">Investment Configuration</CardTitle>
          <CardDescription className="text-zinc-400">Enter your available SkyBlock coins budget.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex gap-4">
            <Input 
              type="number"
              placeholder="e.g. 10000000" 
              value={budget} 
              onChange={(e) => setBudget(e.target.value)} 
              className="bg-zinc-800 border-zinc-700 text-zinc-100"
            />
            <Button disabled={loading} onClick={handleOptimize} className="bg-[#39FF14] text-black hover:bg-[#32e012] min-w-32">
              {loading ? "Computing..." : "Run Engine"}
            </Button>
          </div>

          <div className="space-y-3">
             <label className="text-xs text-zinc-500 font-mono uppercase tracking-wider">Investment Strategy</label>
             <div className="flex items-center space-x-4">
                <Button 
                   variant="outline" 
                   size="sm"
                   className={`flex-1 h-10 border-zinc-700 transition-all ${investmentMode === 'lazy' ? 'bg-[#39FF14] text-black border-[#39FF14] scale-[1.02]' : 'bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'}`}
                   onClick={() => setInvestmentMode("lazy")}
                >
                   🟢 Lazy Investor (Insta-Buy)
                </Button>
                <Button 
                   variant="outline" 
                   size="sm"
                   className={`flex-1 h-10 border-zinc-700 transition-all ${investmentMode === 'flipper' ? 'bg-[#f43f5e] text-white border-[#f43f5e] scale-[1.02]' : 'bg-transparent text-zinc-500 hover:text-zinc-100 hover:bg-zinc-800'}`}
                   onClick={() => setInvestmentMode("flipper")}
                >
                   🔴 Margin Flipper (Buy Orders)
                </Button>
             </div>
          </div>

          <div className="space-y-3 border-t border-zinc-800 pt-4">
             <label className="text-xs text-zinc-500 font-mono uppercase tracking-wider">Bazaar Tax Rate</label>
             <div className="flex items-center space-x-2">
                {[
                  { label: "Standard (1.25%)", val: 0.0125 },
                  { label: "Upgraded (1.0%)", val: 0.01 },
                  { label: "Derpy (5.0%)", val: 0.05 }
                ].map(({ label, val }) => (
                   <Button 
                      key={label}
                      variant="outline" 
                      size="sm"
                      className={`flex-1 h-8 text-[10px] uppercase border-zinc-700 transition-all ${Math.abs(taxRate - val) < 0.0001 ? 'bg-zinc-100 text-black border-zinc-100' : 'bg-transparent text-zinc-500 hover:bg-zinc-800'}`}
                      onClick={() => setTaxRate(val)}
                   >
                      {label}
                   </Button>
                ))}
             </div>
          </div>
        </CardContent>
      </Card>

      {result && result.status === "optimal" && (
        <Card className="bg-zinc-900 border-zinc-800 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <CardHeader>
             <div className="flex justify-between items-start">
                 <div>
                    <CardTitle className="text-zinc-100 font-vt323 text-2xl">Optimal Allocation Plan</CardTitle>
                    <p className="text-zinc-400 text-sm mt-1">Expected Net ROI: <span className="text-[#39FF14] font-bold">{(Number(result.expected_portfolio_roi ?? 0) * 100).toFixed(2)}%</span></p>
                 </div>
                 <div className="text-right font-vt323">
                    <p className="text-zinc-400 text-sm">Allocated / Budget</p>
                    <p className="text-[#39FF14] text-xl">{formatNum(result.total_spent)} / {formatNum(result.budget_provided)}</p>
                 </div>
             </div>
             <div className="mt-4 p-3 bg-[#39FF14]/10 border border-[#39FF14]/30 rounded-lg flex items-center gap-3">
                <span className="text-xl">ℹ️</span>
                <div className="text-xs text-zinc-300 leading-relaxed">
                   <p><span className="text-[#39FF14] font-bold">Tax-Aware Strategy Enabled:</span> Profits are calculated <span className="underline">NET</span> of the {((result.tax_rate ?? taxRate) * 100).toFixed(2)}% Bazaar tax.</p>
                   <p className="mt-1 opacity-70 italic">Diversification & Strict Liquidity Guard (10%) are active. Items with 0 volume are excluded.</p>
                </div>
             </div>
          </CardHeader>
          <CardContent>
             <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800">
                    <TableHead className="text-zinc-400">Item ID</TableHead>
                    <TableHead className="text-zinc-400 text-right">Quantity</TableHead>
                    <TableHead className="text-zinc-400 text-right">Market Cap (10%)</TableHead>
                    <TableHead className="text-zinc-400 text-right">{investmentMode === 'lazy' ? 'Insta-Buy' : 'Buy Order'}</TableHead>
                    <TableHead className="text-zinc-400 text-right">Total Cost</TableHead>
                    <TableHead className="text-[#39FF14] text-right">Net Profit</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.allocations?.map((alloc: any, idx: number) => (
                    <TableRow key={alloc.item_id || idx} className="border-zinc-800/50 hover:bg-zinc-800/50 transition-colors">
                      <TableCell className="font-medium text-zinc-100">{alloc.item_id || "Unknown"}</TableCell>
                      <TableCell className="text-right text-zinc-300">{formatNum(alloc.quantity)}</TableCell>
                      <TableCell className="text-right text-zinc-500 text-xs italic">
                         {formatNum(alloc.volume_cap_applied)} units
                      </TableCell>
                      <TableCell className="text-right text-zinc-300">{formatNum(alloc.unit_price, 1)}</TableCell>
                      <TableCell className="text-right text-zinc-300">{formatNum(alloc.total_cost, 1)}</TableCell>
                      <TableCell className="text-right text-[#39FF14] font-bold drop-shadow-[0_0_8px_rgba(57,255,20,0.5)]">
                         +{formatNum(alloc.total_expected_profit, 1)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
             </Table>
          </CardContent>
        </Card>
      )}
      
      {result && result.error && (
         <div className="p-4 bg-red-900/20 border border-red-900/50 rounded-lg text-red-400 text-sm font-medium animate-in fade-in">
            {typeof result.error === 'string' ? result.error : JSON.stringify(result.error)}
         </div>
      )}
    </div>
  );
}
