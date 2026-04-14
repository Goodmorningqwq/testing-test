"use client";
import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const [search, setSearch] = useState("");
  const [selectedItem, setSelectedItem] = useState("ENCHANTED_DIAMOND");
  const [history, setHistory] = useState<any[]>([]);
  const [prediction, setPrediction] = useState<any>(null);

  useEffect(() => {
    if (selectedItem) {
      fetch(`${API_BASE_URL}/api/history/${selectedItem}?days=14`)
        .then(res => res.json())
        .then(data => {
          if(Array.isArray(data)) {
            const formatted = data.map(d => ({
               time: new Date(d.timestamp).toLocaleDateString(),
               price: d.sell_price
            }));
            setHistory(formatted);
          }
        })
        .catch(console.error);
        
      setPrediction(null);
      fetch(`${API_BASE_URL}/api/predict/${selectedItem}?horizon_days=7`)
        .then(res => res.json())
        .then(data => {
            if (!data.detail) {
               setPrediction(data);
            }
        })
        .catch(console.error);
    }
  }, [selectedItem]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Bazaar Terminal</h1>
        <p className="text-zinc-400">Search assets and view ML-calibrated predictions.</p>
      </div>

      <div className="flex gap-4">
        <Input 
          placeholder="Search items... (e.g. ENCHANTED_IRON)" 
          value={search} 
          onChange={(e) => setSearch(e.target.value)} 
          className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-sm"
        />
        <Button onClick={() => setSelectedItem(search.toUpperCase() || "ENCHANTED_DIAMOND")} className="bg-[#39FF14] text-black hover:bg-[#32e012]">
          Analyze
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="col-span-2 bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100 font-vt323 uppercase tracking-wider">{selectedItem} - 14 Day History</CardTitle>
          </CardHeader>
          <CardContent className="h-[400px]">
             {history.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="time" stroke="#a1a1aa" />
                    <YAxis stroke="#a1a1aa" domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', color: '#fff' }} />
                    <Line type="monotone" dataKey="price" stroke="#39FF14" strokeWidth={2} dot={false} />
                </LineChart>
                </ResponsiveContainer>
             ) : (
                <div className="w-full h-full flex items-center justify-center text-zinc-500">Loading historical data...</div>
             )}
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100 font-vt323 tracking-wider">AI Forecast</CardTitle>
            <CardDescription className="text-zinc-400">7-Day Horizon Prophet Model</CardDescription>
          </CardHeader>
          <CardContent>
            {prediction ? (
              <div className="space-y-6">
                <div>
                  <p className="text-sm text-zinc-400">Current Price</p>
                  <p className="text-2xl font-bold font-vt323 text-zinc-100">{prediction.current_price?.toLocaleString(undefined, {maximumFractionDigits: 1})} coins</p>
                </div>
                <div>
                  <p className="text-sm text-zinc-400">Predicted (7d)</p>
                  <p className="text-2xl font-bold font-vt323 text-[#39FF14]">{prediction.predicted_end_price?.toLocaleString(undefined, {maximumFractionDigits: 1})} coins</p>
                </div>
                <div>
                  <p className="text-sm text-zinc-400">Predicted ROI</p>
                  <p className={`text-xl font-bold font-vt323 ${prediction.calibrated_roi >= 0 ? 'text-[#39FF14]' : 'text-red-500'}`}>
                    {(prediction.calibrated_roi * 100).toFixed(2)}%
                  </p>
                </div>
                {prediction.calibration_factor_applied !== 1.0 && (
                  <div className="p-3 bg-zinc-800/50 border border-zinc-700 rounded text-xs text-zinc-300">
                    * Using personal calibration factor of {prediction.calibration_factor_applied.toFixed(2)}X 
                    based on your past log accuracy.
                  </div>
                )}
              </div>
            ) : (
               <p className="text-zinc-400 text-sm animate-pulse">Loading prediction...</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
