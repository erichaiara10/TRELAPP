import React, { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend } from "recharts";

const COLORS = ["#2A5B46","#C86A4C","#204838","#E6A48C","#7DA893","#F59E0B"];

export default function Reports() {
  const [summary, setSummary] = useState({});
  const [sources, setSources] = useState([]);
  useEffect(() => {
    api.get("/reports/summary").then((r) => setSummary(r.data));
    api.get("/reports/leads_by_source").then((r) => setSources(r.data));
  }, []);
  const portfolio = useMemo(() => ([
    { name: "Active", value: summary.properties_active || 0 },
    { name: "Sold", value: summary.properties_sold || 0 },
    { name: "Leased", value: summary.properties_leased || 0 },
  ]), [summary]);
  return (
    <div>
      <h1 className="text-2xl font-semibold">Reports</h1>
      <div className="mt-4 grid md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="text-sm font-medium mb-3">Leads by source</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sources}><XAxis dataKey="source" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Bar dataKey="count" fill="#2A5B46" /></BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="text-sm font-medium mb-3">Portfolio</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={portfolio} dataKey="value" outerRadius={90} label>
                  {[0,1,2].map((i) => <Cell key={i} fill={COLORS[i]} />)}
                </Pie>
                <Legend /><Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="mt-4 grid md:grid-cols-4 gap-3 text-sm">
        {Object.entries(summary).map(([k, v]) => (
          <div key={k} className="bg-white rounded-lg border border-border p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">{k.replace(/_/g," ")}</div>
            <div className="text-2xl font-semibold mt-1">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
