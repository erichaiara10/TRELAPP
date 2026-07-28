import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import StatsGrid from "@/components/admin/StatsGrid";

const BAR_RADIUS = [4, 4, 0, 0];

export default function Dashboard() {
  const [summary, setSummary] = useState({});
  const [sources, setSources] = useState([]);
  const [leads, setLeads] = useState([]);
  useEffect(() => {
    api.get("/reports/summary").then((r) => setSummary(r.data));
    api.get("/reports/leads_by_source").then((r) => setSources(r.data));
    api.get("/leads").then((r) => setLeads(r.data.slice(0, 5)));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold" data-testid="dashboard-title">Dashboard</h1>
      <p className="text-sm text-muted-foreground">Overview of today&apos;s operations.</p>
      <div className="mt-6">
        <StatsGrid summary={summary} />
      </div>
      <div className="mt-8 grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-lg border border-border p-4">
          <div className="text-sm font-medium">Leads by source</div>
          <div className="h-64 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sources}>
                <XAxis dataKey="source" fontSize={11} />
                <YAxis fontSize={11} />
                <Tooltip />
                <Bar dataKey="count" fill="#2A5B46" radius={BAR_RADIUS} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="text-sm font-medium mb-3">Recent leads</div>
          <div className="space-y-2">
            {leads.map((l) => (
              <Link key={l.id} to="/admin/leads" className="block p-2 rounded hover:bg-sand-50 border border-transparent hover:border-border" data-testid={`recent-lead-${l.id}`}>
                <div className="text-sm font-medium">{l.name}</div>
                <div className="text-xs text-muted-foreground">{l.source} · {l.status}</div>
              </Link>
            ))}
            {leads.length === 0 && <div className="text-xs text-muted-foreground">No leads yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
