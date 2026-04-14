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

  const handleOptimize = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget: parseFloat(budget), horizon_days: 7, candidate_items: [] })
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      setResult({ error: "Failed to connect to optimization engine." });
    }
    setLoading(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Portfolio Optimizer</h1>
        <p className="text-zinc-400">Run the PuLP Linear Programming engine to find the exact optimal purchase allocations.</p>
      </div>

      <Card className="bg-zinc-900 border-zinc-800 max-w-xl">
        <CardHeader>
          <CardTitle className="text-zinc-100 font-vt323">Investment Configuration</CardTitle>
          <CardDescription className="text-zinc-400">Enter your available SkyBlock coins budget.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Input 
              type="number"
              placeholder="e.g. 10000000" 
              value={budget} 
              onChange={(e) => setBudget(e.target.value)} 
              className="bg-zinc-800 border-zinc-700 text-zinc-100"
            />
            <Button disabled={loading || !budget} onClick={handleOptimize} className="bg-[#39FF14] text-black hover:bg-[#32e012] min-w-32">
              {loading ? "Computing..." : "Run Engine"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && result.status === "optimal" && (
        <Card className="bg-zinc-900 border-zinc-800 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <CardHeader>
             <div className="flex justify-between items-start">
                 <div>
                    <CardTitle className="text-zinc-100 font-vt323 text-2xl">Optimal Allocation Plan</CardTitle>
                    <p className="text-zinc-400 text-sm mt-1">Expected ROI: <span className="text-[#39FF14] font-bold">{(result.expected_portfolio_roi * 100).toFixed(2)}%</span></p>
                 </div>
                 <div className="text-right font-vt323">
                    <p className="text-zinc-400 text-sm">Allocated / Budget</p>
                    <p className="text-[#39FF14] text-xl">{result.total_spent.toLocaleString()} / {result.budget_provided.toLocaleString()}</p>
                 </div>
             </div>
          </CardHeader>
          <CardContent>
             <Table>
               <TableHeader>
                 <TableRow className="border-zinc-800">
                   <TableHead className="text-zinc-400">Item ID</TableHead>
                   <TableHead className="text-zinc-400 text-right">Quantity</TableHead>
                   <TableHead className="text-zinc-400 text-right">Unit Price</TableHead>
                   <TableHead className="text-zinc-400 text-right">Total Cost</TableHead>
                   <TableHead className="text-[#39FF14] text-right">Expected Profit</TableHead>
                 </TableRow>
               </TableHeader>
               <TableBody>
                 {result.allocations.map((alloc: any) => (
                   <TableRow key={alloc.item_id} className="border-zinc-800/50 hover:bg-zinc-800/50 transition-colors">
                     <TableCell className="font-medium text-zinc-100">{alloc.item_id}</TableCell>
                     <TableCell className="text-right text-zinc-300">{alloc.quantity.toLocaleString()}</TableCell>
                     <TableCell className="text-right text-zinc-300">{alloc.unit_price.toLocaleString(undefined, {maximumFractionDigits:1})}</TableCell>
                     <TableCell className="text-right text-zinc-300">{alloc.total_cost.toLocaleString(undefined, {maximumFractionDigits:1})}</TableCell>
                     <TableCell className="text-right text-[#39FF14] drop-shadow-[0_0_8px_rgba(57,255,20,0.5)]">+{alloc.total_expected_profit.toLocaleString(undefined, {maximumFractionDigits:1})}</TableCell>
                   </TableRow>
                 ))}
               </TableBody>
             </Table>
          </CardContent>
        </Card>
      )}
      
      {result && result.error && (
         <div className="p-4 bg-red-900/20 border border-red-900/50 rounded-lg text-red-400 text-sm font-medium animate-in fade-in">
            {result.error}
         </div>
      )}
    </div>
  );
}
