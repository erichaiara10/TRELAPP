// 6. Duplicate Matches — the matcher's review queue and confirmed-match view.
// Live table reads from /api/admin/market/matches; review cases (probable /
// possible / conflict) read from /api/admin/market/review-cases. The full
// per-signal breakdown + confirm/reject flow lands with the matcher (Phase B).
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, KpiCard, Section, PhaseBanner } from "./_shared";

const TABS = [
  { key: "probable", label: "Probable Matches" },
  { key: "conflict", label: "Conflict Cases" },
  { key: "confirmed", label: "Confirmed Matches" },
  { key: "possible", label: "Possible Matches" },
];

export default function DuplicateMatches() {
  const [tab, setTab] = useState("probable");
  const [summary, setSummary] = useState({});
  const [cases, setCases] = useState([]);
  const [matches, setMatches] = useState([]);

  useEffect(() => {
    api.get("/admin/market/summary").then((r) => setSummary(r.data)).catch(() => {});
    api.get("/admin/market/matches?status=active&limit=100").then((r) => setMatches(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab === "confirmed") return;
    api.get(`/admin/market/review-cases?status=open&case_type=${tab}&limit=100`)
      .then((r) => setCases(r.data || [])).catch(() => setCases([]));
  }, [tab]);

  return (
    <div data-testid="market-duplicates-page">
      <PageHeader
        title="Duplicate Matches"
        subtitle="Review queue for probable / possible / conflict matches surfaced by the identity matcher (MATCH-1.0). Confirmed matches land in the confirmed tab."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KpiCard label="Active Matches" value={summary.matches_active} testid="kpi-dup-active" />
        <KpiCard label="Open Review Cases" value={summary.review_cases_open} testid="kpi-dup-open" />
        <KpiCard label="Master Properties" value={summary.master_properties} testid="kpi-dup-masters" />
        <KpiCard label="Audit Events" value={summary.audit_events} testid="kpi-dup-audit" />
      </div>

      <div className="flex gap-2 mb-3" data-testid="duplicates-tabs">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
                  data-testid={`dup-tab-${t.key}`}
                  className={`px-3 py-1.5 text-sm rounded-md border ${tab === t.key ? "bg-[#0F172A] text-white border-[#0F172A]" : "border-border bg-white"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "confirmed" ? (
        <Section title="Confirmed Matches" testid="dup-confirmed-section">
          {matches.length === 0 ? (
            <div className="text-sm text-muted-foreground py-6 text-center">No confirmed matches yet. New matches will appear here once the matcher (Phase B) starts writing to the property_matches collection.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Match</th>
                  <th className="py-2 pr-3">Listing</th>
                  <th className="py-2 pr-3">Master</th>
                  <th className="py-2 pr-3">Method</th>
                  <th className="py-2 pr-3">Band</th>
                  <th className="py-2 pr-3">Score</th>
                </tr>
              </thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.id} className="border-b border-border/60" data-testid={`match-row-${m.id}`}>
                    <td className="py-2 pr-3 font-mono text-xs">{m.id.slice(0, 8)}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{m.market_listing_id?.slice(0, 8)}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{m.master_property_id?.slice(0, 8) || "—"}</td>
                    <td className="py-2 pr-3">{m.method}</td>
                    <td className="py-2 pr-3 uppercase text-xs tracking-widest">{m.decision_band}</td>
                    <td className="py-2 pr-3 tabular-nums">{m.score?.toFixed?.(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      ) : (
        <Section title={`${TABS.find((t) => t.key === tab)?.label} Queue`} testid={`dup-queue-${tab}`}>
          {cases.length === 0 ? (
            <div className="text-sm text-muted-foreground py-6 text-center">No open {tab} cases. Cases will appear here once the matcher (Phase B) surfaces ambiguous matches for review.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Case</th>
                  <th className="py-2 pr-3">Score</th>
                  <th className="py-2 pr-3">Listing</th>
                  <th className="py-2 pr-3">Proposed Master</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id} className="border-b border-border/60" data-testid={`case-row-${c.id}`}>
                    <td className="py-2 pr-3 font-mono text-xs">{c.id.slice(0, 8)}</td>
                    <td className="py-2 pr-3 tabular-nums">{c.score ?? "—"}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{c.market_listing_id?.slice(0, 8) || "—"}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{c.proposed_master_property_id?.slice(0, 8) || "—"}</td>
                    <td className="py-2 pr-3 uppercase text-xs tracking-widest">{c.status}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{c.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      )}

      <div className="mt-4">
        <PhaseBanner phase="Phase B — Matcher">
          Per-case detail pane (signal breakdown, evidence, side-by-side compare, confirm / reject / defer actions) ships with MATCH-1.0 execution.
        </PhaseBanner>
      </div>
    </div>
  );
}
