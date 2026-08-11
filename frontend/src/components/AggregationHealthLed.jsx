// Aggregation Health LED — small live badge that polls the source-strip
// analytics endpoint. Colour reflects the worst source status across the
// last 30 days so operators spot pipeline stalls on every screen.
//   green  → every active source has success_rate ≥ 90% or no runs yet
//   amber  → any source below 90% OR any partial in last 24h
//   red    → any source with a consecutive-failure streak ≥ 2
// Tooltip on hover surfaces the per-source counts.
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

const POLL_MS = 60_000;

export default function AggregationHealthLed() {
  const [strip, setStrip] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await api.get("/admin/market/analytics/source-strip");
        if (!cancelled) setStrip(data || []);
      } catch { /* stay silent — LED shows grey */ }
    };
    load();
    const t = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  if (!strip) {
    return <Led color="#9CA3AF" label="…" tooltip="Loading pipeline health" />;
  }
  const active = strip.filter((s) => s.active);
  if (active.length === 0) {
    return <Led color="#9CA3AF" label="0" tooltip="No active data sources — visit /admin/market/sources to configure one" />;
  }
  const worstStreak = Math.max(0, ...active.map((s) => s.consecutive_failures || 0));
  const lowest = active.filter((s) => s.success_rate != null)
                       .reduce((m, s) => Math.min(m, s.success_rate), 100);
  let color = "#10B981", status = "Healthy";
  if (worstStreak >= 2) { color = "#DC2626"; status = "Failing"; }
  else if (lowest < 90) { color = "#F59E0B"; status = "Degraded"; }

  const summary = active.map((s) =>
    `${s.name}: ${s.success_rate == null ? "no runs" : `${s.success_rate}%`}` +
    (s.consecutive_failures ? ` · ${s.consecutive_failures} fail streak` : "")
  ).join("\n");

  return <Led color={color} label={`${active.length}`} tooltip={`Pipeline: ${status}\n\n${summary}`} />;
}

function Led({ color, label, tooltip }) {
  return (
    <Link to="/admin/market" title={tooltip}
          className="flex items-center gap-2 px-2 py-1 rounded bg-white/5 hover:bg-white/10 transition-colors"
          data-testid="agg-health-led">
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-40"
              style={{ background: color }} />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5" style={{ background: color }} />
      </span>
      <span className="text-[10px] uppercase tracking-widest text-white/70">Pipeline</span>
      <span className="text-xs font-medium tabular-nums">{label}</span>
    </Link>
  );
}
