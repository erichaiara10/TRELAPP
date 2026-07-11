import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

const Stat = ({ label, value, hint, to }) => {
  const Wrap = to ? Link : "div";
  return (
    <Wrap to={to} className="bg-white rounded-lg border border-border p-4 hover:shadow-sm block" data-testid={`stat-${label.toLowerCase().replace(/\s+/g,'-')}`}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-3xl font-semibold mt-1">{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </Wrap>
  );
};

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
      <p className="text-sm text-muted-foreground">Overview of today's operations.</p>
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Active properties" value={summary.properties_active ?? "–"} to="/admin/properties" />
        <Stat label="New leads" value={summary.leads_new ?? "–"} to="/admin/leads" />
        <Stat label="Open inspections" value={summary.inspections_open ?? "–"} to="/admin/inspections" />
        <Stat label="Open tasks" value={summary.tasks_open ?? "–"} to="/admin/tasks" />
        <Stat label="Customers" value={summary.customers ?? "–"} to="/admin/customers" />
        <Stat label="Active requirements" value={summary.requirements_active ?? "–"} to="/admin/requirements" />
        <Stat label="Sold" value={summary.properties_sold ?? "–"} />
        <Stat label="Leased" value={summary.properties_leased ?? "–"} />
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
                <Bar dataKey="count" fill="#2A5B46" radius={[4, 4, 0, 0]} />
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
