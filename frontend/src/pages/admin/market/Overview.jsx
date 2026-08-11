// 1. Overview — live dashboard with source-health strip, price-trend chart
// and quick-insights donuts. All widgets pull from the analytics endpoints;
// widgets degrade gracefully to their empty-state until scrapers produce data.
import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { api, money } from "@/lib/api";
import { PageHeader, KpiCard, Section } from "./_shared";

const PIE_COLORS = ["#2A5B46", "#4B8B70", "#7BB593", "#B5DAB8", "#DDE9D1", "#F1B24A"];

export default function MarketOverview() {
  const [s, setS] = useState({});
  const [strip, setStrip] = useState([]);
  const [trend, setTrend] = useState([]);
  const [insights, setInsights] = useState({});
  const [cases, setCases] = useState([]);

  useEffect(() => {
    api.get("/admin/market/summary").then((r) => setS(r.data)).catch(() => {});
    api.get("/admin/market/analytics/source-strip").then((r) => setStrip(r.data || [])).catch(() => {});
    api.get("/admin/market/analytics/price-trends?purpose=sale&months=12").then((r) => setTrend(r.data || [])).catch(() => {});
    api.get("/admin/market/analytics/quick-insights").then((r) => setInsights(r.data || {})).catch(() => {});
    api.get("/admin/market/review-cases?status=open&limit=5").then((r) => setCases(r.data || [])).catch(() => {});
  }, []);

  return (
    <div data-testid="market-overview-page">
      <PageHeader
        title="Overview"
        subtitle="Live pipeline snapshot — sources, listings, master identities, matches, review workload, active configuration."
      />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5" data-testid="market-overview-kpis">
        <KpiCard label="Master Properties" value={s.master_properties} testid="kpi-masters" />
        <KpiCard label="Active Listings" value={s.active_listings} hint={`${s.market_listings || 0} total`} testid="kpi-active-listings" />
        <KpiCard label="Active Matches" value={s.matches_active} testid="kpi-matches" />
        <KpiCard label="Open Review" value={s.review_cases_open} testid="kpi-review-cases" />
        <KpiCard label="Data Sources" value={`${s.active_sources ?? 0}/${s.sources ?? 0}`} hint="active / total" testid="kpi-sources" />
        <KpiCard label="Active Config" value={s.active_config_version} testid="kpi-config" />
      </div>

      {/* Source health strip */}
      <Section title="Source Health (last 30 days)" testid="overview-source-strip">
        {strip.length === 0 ? (
          <div className="text-sm text-muted-foreground">No sources configured yet.</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {strip.map((s) => {
              const rate = s.success_rate;
              const color = rate == null ? "#9CA3AF"
                : rate >= 90 ? "#10B981"
                : rate >= 60 ? "#F59E0B" : "#DC2626";
              return (
                <div key={s.source_id} className="border border-border rounded p-3 bg-white"
                     data-testid={`strip-${s.source_id}`}>
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                    <div className="font-medium truncate">{s.name}</div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{s.collector || "seed"} · {s.runs} runs</div>
                  <div className="mt-2 text-sm">
                    <span className="font-medium tabular-nums">{rate == null ? "—" : `${rate}%`}</span>
                    <span className="text-xs text-muted-foreground ml-2">{s.listings_ingested} listings</span>
                  </div>
                  {s.consecutive_failures > 0 && (
                    <div className="text-xs text-red-700 mt-1">{s.consecutive_failures} fails in a row</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {/* Charts row */}
      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        <div className="lg:col-span-2">
          <Section title="Sale price trend — median (12 months)" testid="overview-trend-chart">
            {trend.length === 0 ? (
              <div className="text-sm text-muted-foreground py-8 text-center">
                No listings yet — the trend chart activates once collectors ingest priced sales.
              </div>
            ) : (
              <div className="h-64" data-testid="trend-chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v) => money(v)} />
                    <Line type="monotone" dataKey="median" stroke="#2A5B46" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Section>
        </div>

        <Section title="Quick Insights" testid="overview-insights">
          {(insights.by_class || []).length === 0 ? (
            <div className="text-sm text-muted-foreground py-6">Insights render once listings exist.</div>
          ) : (
            <div className="space-y-4">
              <MiniDonut title="By Class" data={insights.by_class} testid="donut-class" />
              <MiniDonut title="By Purpose" data={insights.by_purpose} testid="donut-purpose" />
              <MiniDonut title="Match Bands" data={insights.match_bands} testid="donut-bands" />
            </div>
          )}
        </Section>
      </div>

      {/* Recent review cases */}
      <div className="mt-4">
        <Section title="Latest Open Review Cases" testid="market-recent-cases">
          {cases.length === 0 ? (
            <div className="text-sm text-muted-foreground">No open review cases.</div>
          ) : (
            <div className="divide-y divide-border text-sm">
              {cases.map((c) => (
                <div key={c.id} className="py-2 flex items-center justify-between" data-testid={`case-row-${c.id}`}>
                  <div>{c.case_type} · <span className="font-mono text-xs">{c.id.slice(0, 8)}…</span></div>
                  <span className="text-xs uppercase tracking-widest">{c.status}</span>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}

function MiniDonut({ title, data, testid }) {
  const rows = (data || []).filter((r) => r.count > 0);
  if (rows.length === 0) return null;
  return (
    <div data-testid={testid}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground mb-1">{title}</div>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={rows} dataKey="count" nameKey="key" innerRadius={30} outerRadius={55}>
              {rows.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            </Pie>
            <Legend layout="vertical" verticalAlign="middle" align="right" iconSize={8}
                    wrapperStyle={{ fontSize: 10 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
