"use client";
import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const [search, setSearch] = useState("");
  const [itemsList, setItemsList] = useState<string[]>([]);
  const [selectedItem, setSelectedItem] = useState("ENCHANTED_DIAMOND");
  const [history, setHistory] = useState<any[]>([]);
  const [prediction, setPrediction] = useState<any>(null);
  const [days, setDays] = useState(1);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/items`)
      .then(res => res.json())
      .then(data => {
        if(Array.isArray(data)) setItemsList(data);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedItem) {
      fetch(`${API_BASE_URL}/api/history/${selectedItem}?days=${days}`)
        .then(res => res.json())
        .then(data => {
          if(Array.isArray(data)) {
            const formatted = data.map(d => ({
               time: new Date(d.timestamp).toLocaleString(undefined, {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}),
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
  }, [selectedItem, days]);

  const filteredItems = itemsList
    .filter(i => i.toLowerCase().includes(search.toLowerCase()))
    .slice(0, 8); // limit top recommendations

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-vt323 tracking-wide text-[#39FF14]">Bazaar Terminal</h1>
        <p className="text-zinc-400">Search assets and view ML-calibrated predictions.</p>
      </div>

      <div className="flex gap-4 relative">
        <div className="relative w-full max-w-sm">
          <Input 
            placeholder="Search items... (e.g. ENCHANTED_IRON)" 
            value={search} 
            onChange={(e) => {
               setSearch(e.target.value);
               setShowDropdown(true);
            }} 
            onFocus={() => setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
            className="bg-zinc-900 border-zinc-800 text-zinc-100 w-full font-mono text-sm"
          />
          {showDropdown && search && filteredItems.length > 0 && (
            <div className="absolute top-12 left-0 w-full bg-zinc-950 border border-zinc-800 rounded-lg shadow-xl z-50 overflow-hidden">
              {filteredItems.map(item => (
                <div 
                  key={item} 
                  className="px-4 py-2 hover:bg-zinc-800 text-sm text-zinc-300 font-mono cursor-pointer transition-colors"
                  onClick={() => {
                     setSearch(item);
                     setSelectedItem(item);
                     setShowDropdown(false);
                  }}
                >
                  {item}
                </div>
              ))}
            </div>
          )}
        </div>
        <Button 
           onClick={() => {
              setSelectedItem(search.toUpperCase() || "ENCHANTED_DIAMOND");
              setShowDropdown(false);
           }} 
           className="bg-[#39FF14] text-black hover:bg-[#32e012]"
        >
          Analyze
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="col-span-2 bg-zinc-900 border-zinc-800 animate-in fade-in duration-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-zinc-100 font-vt323 uppercase tracking-wider text-xl mt-1">{selectedItem} - {days} DAY HISTORY</CardTitle>
            <div className="flex space-x-2">
               {[1, 7, 14].map(d => (
                  <Button 
                    key={d} 
                    variant="outline" 
                    size="sm"
                    className={`h-7 px-3 text-xs font-mono border-zinc-800 transition-colors ${days === d ? 'bg-[#39FF14]/20 text-[#39FF14] border-[#39FF14]/50' : 'bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'}`}
                    onClick={() => setDays(d)}
                  >
                    {d} {d===1 ? 'Day' : 'Days'}
                  </Button>
               ))}
            </div>
          </CardHeader>
          <CardContent className="h-[400px]">
             {history.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis dataKey="time" stroke="#a1a1aa" fontSize={12} tickMargin={10} minTickGap={30} />
                    <YAxis stroke="#a1a1aa" domain={['auto', 'auto']} fontSize={12} tickFormatter={(value) => value.toLocaleString()} />
                    <Tooltip 
                       contentStyle={{ backgroundColor: '#18181b', borderColor: '#39FF14', color: '#fff', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)' }} 
                       labelStyle={{ color: '#a1a1aa', marginBottom: '4px', fontSize: '12px' }}
                       formatter={(value: any) => [`${parseFloat(value).toLocaleString(undefined, {maximumFractionDigits:1})} coins`, "Price"]}
                    />
                    <Line type="monotone" dataKey="price" stroke="#39FF14" strokeWidth={2} dot={false} activeDot={{ r: 6, fill: '#39FF14', stroke: '#18181b', strokeWidth: 2 }} animationDuration={1000} />
                </LineChart>
                </ResponsiveContainer>
             ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-zinc-500">
                    <p className="animate-pulse">Loading historical data...</p>
                    <p className="text-xs text-zinc-600 mt-2">Waiting for first background poller sync.</p>
                </div>
             )}
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800 animate-in slide-in-from-right-4 duration-500">
          <CardHeader>
            <CardTitle className="text-zinc-100 font-vt323 tracking-wider text-xl">AI Forecast</CardTitle>
            <CardDescription className="text-zinc-400">7-Day Horizon Prophet Model</CardDescription>
          </CardHeader>
          <CardContent>
            {prediction ? (
              <div className="space-y-6">
                <div>
                  <p className="text-sm text-zinc-400">Current Price</p>
                  <p className="text-3xl font-bold font-vt323 text-zinc-100">{prediction.current_price?.toLocaleString(undefined, {maximumFractionDigits: 1})} coins</p>
                </div>
                <div>
                  <p className="text-sm text-zinc-400">Predicted (7d)</p>
                  <p className="text-3xl font-bold font-vt323 text-[#39FF14]">{prediction.predicted_end_price?.toLocaleString(undefined, {maximumFractionDigits: 1})} coins</p>
                </div>
                <div>
                  <p className="text-sm text-zinc-400">Predicted ROI</p>
                  <p className={`text-2xl font-bold font-vt323 ${prediction.calibrated_roi >= 0 ? 'text-[#39FF14] drop-shadow-[0_0_8px_rgba(57,255,20,0.5)]' : 'text-red-500'}`}>
                    {(prediction.calibrated_roi * 100).toFixed(2)}%
                  </p>
                </div>
                {prediction.calibration_factor_applied !== 1.0 && (
                  <div className="p-3 bg-zinc-800/50 border border-zinc-800 rounded text-xs text-zinc-400">
                    * Using personal calibration factor of <span className="text-zinc-200">{prediction.calibration_factor_applied.toFixed(2)}X</span> 
                    based on your past log accuracy.
                  </div>
                )}
              </div>
            ) : (
               <div className="space-y-4">
                  <p className="text-zinc-400 text-sm animate-pulse">Loading prediction...</p>
                  <div className="h-4 bg-zinc-800 rounded w-3/4 animate-pulse"></div>
                  <div className="h-4 bg-zinc-800 rounded w-1/2 animate-pulse"></div>
                  <div className="h-4 bg-zinc-800 rounded w-5/6 animate-pulse"></div>
               </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
