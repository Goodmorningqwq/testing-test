"use client";
import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function HistoryPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  
  // Form State
  const [planId, setPlanId] = useState("");
  const [recommended, setRecommended] = useState("");
  const [budget, setBudget] = useState("");
  const [horizon, setHorizon] = useState("7");
  const [predictedRoi, setPredictedRoi] = useState("");
  const [actualRoi, setActualRoi] = useState("");
  const [actualProfit, setActualProfit] = useState("");
  const [notes, setNotes] = useState("");

  const fetchLogs = () => {
    fetch(`${API_BASE_URL}/api/logs`)
      .then(res => res.json())
      .then(data => {
         if(Array.isArray(data)) setLogs(data);
      })
      .catch(console.error);
  };

  useEffect(() => {
    fetchLogs();
    setPlanId(`PLAN-${Date.now().toString().slice(-6)}`);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE_URL}/api/logs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
           plan_id: planId,
           recommended_items: recommended,
           budget: parseFloat(budget),
           horizon_days: parseInt(horizon),
           predicted_roi: parseFloat(predictedRoi) / 100, // convert % input
           actual_roi: parseFloat(actualRoi) / 100,
           actual_profit: parseFloat(actualProfit),
           notes: notes
        })
      });
      if (res.ok) {
        setOpen(false);
        fetchLogs();
        setPlanId(`PLAN-${Date.now().toString().slice(-6)}`);
      }
    } catch (err) {
      console.error("Failed to submit feedback", err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
         <div className="flex flex-col gap-2">
           <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Activity Log & Feedback</h1>
           <p className="text-zinc-400">Past optimizations and actual recorded outcomes to auto-calibrate future ML predictions.</p>
         </div>
         <Dialog open={open} onOpenChange={setOpen}>
           <DialogTrigger render={
             <Button className="bg-[#39FF14] text-black hover:bg-[#32e012] mb-1 font-vt323 text-lg tracking-wide">
               + Log Outcome
             </Button>
           } />
           <DialogContent className="bg-zinc-950 border-zinc-800 text-zinc-100 sm:max-w-[425px]">
             <DialogHeader>
               <DialogTitle className="font-vt323 text-2xl text-[#39FF14]">Log Investment Outcome</DialogTitle>
               <DialogDescription className="text-zinc-400">
                 This data acts as a feedback loop. Your actual ROI drives the calibration factor for future AI predictions.
               </DialogDescription>
             </DialogHeader>
             <form onSubmit={handleSubmit} className="grid gap-4 py-4">
               <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                     <Label className="text-zinc-400">Plan ID</Label>
                     <Input value={planId} onChange={e => setPlanId(e.target.value)} className="bg-zinc-900 border-zinc-800" />
                  </div>
                  <div className="space-y-2">
                     <Label className="text-zinc-400">Horizon (Days)</Label>
                     <Input type="number" value={horizon} onChange={e => setHorizon(e.target.value)} className="bg-zinc-900 border-zinc-800" required />
                  </div>
               </div>
               <div className="grid grid-cols-2 gap-4">
                 <div className="space-y-2">
                   <Label className="text-zinc-400">Original Budget</Label>
                   <Input type="number" value={budget} onChange={e => setBudget(e.target.value)} className="bg-zinc-900 border-zinc-800" required />
                 </div>
                 <div className="space-y-2">
                   <Label className="text-zinc-400">Actual Profit</Label>
                   <Input type="number" value={actualProfit} onChange={e => setActualProfit(e.target.value)} className="bg-zinc-900 border-zinc-800" required />
                 </div>
               </div>
               <div className="grid grid-cols-2 gap-4">
                 <div className="space-y-2">
                   <Label className="text-zinc-400">Expected ROI (%)</Label>
                   <Input type="number" step="0.01" value={predictedRoi} onChange={e => setPredictedRoi(e.target.value)} className="bg-zinc-900 border-zinc-800" required />
                 </div>
                 <div className="space-y-2">
                   <Label className="text-zinc-400">Actual ROI (%)</Label>
                   <Input type="number" step="0.01" value={actualRoi} onChange={e => setActualRoi(e.target.value)} className="bg-zinc-900 border-zinc-800" required />
                 </div>
               </div>
               <div className="space-y-2">
                  <Label className="text-zinc-400">Items (Optional)</Label>
                  <Input value={recommended} onChange={e => setRecommended(e.target.value)} className="bg-zinc-900 border-zinc-800" placeholder="e.g. SLIME, DIAMOND" />
               </div>
               <Button type="submit" className="bg-[#39FF14] text-black w-full hover:bg-[#32e012] mt-4 font-vt323 text-lg tracking-wider">
                  Submit Feedback Loop
               </Button>
             </form>
           </DialogContent>
         </Dialog>
      </div>

      <Card className="bg-zinc-900 border-zinc-800 overflow-hidden">
        <CardContent className="p-0">
          <Table>
               <TableHeader>
                 <TableRow className="border-zinc-800 bg-zinc-950/80">
                   <TableHead className="text-zinc-400 font-medium">Logged At</TableHead>
                   <TableHead className="text-zinc-400 font-medium">Plan ID</TableHead>
                   <TableHead className="text-zinc-400 font-medium text-right">Budget</TableHead>
                   <TableHead className="text-zinc-400 font-medium text-right">Actual Profit</TableHead>
                   <TableHead className="text-zinc-400 font-medium text-right">Predicted ROI</TableHead>
                   <TableHead className="text-[#39FF14] font-medium text-right">Actual ROI</TableHead>
                 </TableRow>
               </TableHeader>
               <TableBody>
                 {logs.map((log: any) => (
                   <TableRow key={log.id} className="border-zinc-800/50 hover:bg-zinc-800/50 transition-colors">
                     <TableCell className="text-zinc-300">{new Date(log.timestamp).toLocaleDateString()}</TableCell>
                     <TableCell className="text-zinc-300 font-vt323 text-lg tracking-wider">{log.plan_id}</TableCell>
                     <TableCell className="text-right text-zinc-300">{log.budget?.toLocaleString()}</TableCell>
                     <TableCell className="text-right text-zinc-300">{log.actual_profit?.toLocaleString()}</TableCell>
                     <TableCell className="text-right text-zinc-400">{(log.predicted_roi * 100).toFixed(2)}%</TableCell>
                     <TableCell className={`text-right font-medium ${log.actual_roi >= log.predicted_roi ? 'text-[#39FF14] drop-shadow-[0_0_8px_rgba(57,255,20,0.5)]' : 'text-red-400'}`}>
                        {(log.actual_roi * 100).toFixed(2)}%
                     </TableCell>
                   </TableRow>
                 ))}
                 {logs.length === 0 && (
                     <TableRow>
                        <TableCell colSpan={6} className="text-center text-zinc-500 py-12">No feedback records found. Log your first outcome to trigger the ML feedback loop.</TableCell>
                     </TableRow>
                 )}
               </TableBody>
             </Table>
        </CardContent>
      </Card>
    </div>
  );
}
