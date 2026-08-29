// 4. Price Trends — median by suburb, 12-month price trend, and
// (suburb × month) heatmap. All pull from /admin/market/analytics/*.
import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  LineChart, Line,
} from "recharts";
import { api, money } from "@/lib/api";
import { PageHeader, Section } from "./_shared";

export default function MarketTrends() {
  const [purpose, setPurpose] = useState("sale");
  const [suburbs, setSuburbs] = useState([]);
  const [trend, setTrend] = useState([]);
  const [heatmap, setHeatmap] = useState({ months: [], suburbs: [], cells: [] });

  useEffect(() => {
    api.get(`/admin/market/analytics/median-by-suburb?purpose=${purpose}`).then((r) => setSuburbs(r.data || [])).catch(() => {});
    api.get(`/admin/market/analytics/price-trends?purpose=${purpose}&months=12`).then((r) => setTrend(r.data || [])).catch(() => {});
    api.get(`/admin/market/analytics/heatmap?purpose=${purpose}&months=12`).then((r) => setHeatmap(r.data || {})).catch(() => {});
  }, [purpose]);

  const heatMax = Math.max(0, ...heatmap.cells.flatMap((row) => heatmap.months.map((m) => Number(row[m] || 0))));
  const cellStyle = (v) => {
    if (!v) return { background: "#F3F4F6" };
    const ratio = Math.min(1, v / (heatMax || 1));
    // Interpolate white → deep green
    const g = Math.round(255 - ratio * 155);
    const rc = Math.round(255 - ratio * 210);
    const bc = Math.round(255 - ratio * 190);
    return { background: `rgb(${rc}, ${g}, ${bc})`, color: ratio > 0.55 ? "#fff" : "#111" };
  };

  return (
    <div data-testid="market-trends-page">
      <PageHeader
        title="Price Trends"
        subtitle="Aggregated median prices across suburbs and time — from the deduplicated Master Property snapshots."
        actions={
          <div className="flex gap-2" data-testid="trends-purpose-tabs">
            {["sale", "rent"].map((p) => (
              <button key={p} onClick={() => setPurpose(p)}
                      data-testid={`trends-purpose-${p}`}
                      className={`px-3 py-1.5 text-sm rounded-md border ${purpose === p ? "bg-[#0F172A] text-white border-[#0F172A]" : "border-border bg-white"}`}>
                {p === "sale" ? "For Sale" : "For Rent"}
              </button>
            ))}
          </div>
        }
      />

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title={`Median ${purpose} price — top suburbs`} testid="trends-median-suburb">
          {suburbs.length === 0 ? (
            <div className="text-sm text-muted-foreground py-6">No data — waiting for collectors.</div>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={suburbs} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <YAxis type="category" dataKey="suburb" tick={{ fontSize: 11 }} width={100} />
                  <Tooltip formatter={(v) => money(v)} />
                  <Bar dataKey="median" fill="#2A5B46" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>

        <Section title={`Median ${purpose} price — 12-month trend`} testid="trends-line">
          {trend.length === 0 ? (
            <div className="text-sm text-muted-foreground py-6">No monthly data yet.</div>
          ) : (
            <div className="h-72">
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

      <div className="mt-4">
        <Section title={`Heatmap — median ${purpose} price by suburb × month`} testid="trends-heatmap">
          {heatmap.cells.length === 0 ? (
            <div className="text-sm text-muted-foreground py-6">No matrix data yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="p-2 text-left text-muted-foreground">Suburb</th>
                    {heatmap.months.map((m) => (
                      <th key={m} className="p-2 text-center text-muted-foreground">{m}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {heatmap.cells.map((row) => (
                    <tr key={row.suburb} data-testid={`heat-row-${row.suburb}`}>
                      <td className="p-2 font-medium whitespace-nowrap">{row.suburb}</td>
                      {heatmap.months.map((m) => (
                        <td key={m} className="p-2 text-center tabular-nums"
                            style={cellStyle(row[m])}>
                          {row[m] ? `${(row[m] / 1000).toFixed(0)}k` : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      </div>

      <div className="mt-4 text-xs text-muted-foreground">
        All price data is aggregated from active listings across configured sources. Figures are indicative and subject to data quality and coverage.
      </div>
    </div>
  );
}
