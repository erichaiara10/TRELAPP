// 1. Overview — live dashboard powered by /api/admin/market/summary.
// Cards mirror the mockup (unique masters, active listings, review queue, etc.)
// Additional widgets from the mockup (charts, recent runs) will slot in as
// Phase E (scrapers) and B (matcher) come online.
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, KpiCard, Section, PhaseBanner } from "./_shared";

export default function MarketOverview() {
  const [s, setS] = useState({});
  const [runs, setRuns] = useState([]);
  const [cases, setCases] = useState([]);
  useEffect(() => {
    api.get("/admin/market/summary").then((r) => setS(r.data)).catch(() => {});
    api.get("/admin/market/runs?limit=5").then((r) => setRuns(r.data || [])).catch(() => {});
    api.get("/admin/market/review-cases?status=open&limit=5").then((r) => setCases(r.data || [])).catch(() => {});
  }, []);

  return (
    <div data-testid="market-overview-page">
      <PageHeader
        title="Overview"
        subtitle="Live health snapshot of the market intelligence pipeline — sources, listings, master identities, matches, review workload, and the active configuration version."
      />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-5" data-testid="market-overview-kpis">
        <KpiCard label="Master Properties" value={s.master_properties} testid="kpi-masters" />
        <KpiCard label="Active Listings" value={s.active_listings} hint={`${s.market_listings || 0} total`} testid="kpi-active-listings" />
        <KpiCard label="Active Matches" value={s.matches_active} testid="kpi-matches" />
        <KpiCard label="Open Review Cases" value={s.review_cases_open} testid="kpi-review-cases" />
        <KpiCard label="Data Sources" value={`${s.active_sources ?? 0}/${s.sources ?? 0}`} hint="active / total" testid="kpi-sources" />
        <KpiCard label="Active Config" value={s.active_config_version} testid="kpi-config" />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Recent Collection Runs" testid="market-recent-runs">
          {runs.length === 0 ? (
            <div className="text-sm text-muted-foreground">No collection runs yet. Configure a data source, then trigger a collection run in Phase E.</div>
          ) : (
            <div className="divide-y divide-border text-sm">
              {runs.map((r) => (
                <div key={r.id} className="py-2 flex items-center justify-between" data-testid={`run-row-${r.id}`}>
                  <div className="truncate">
                    <div className="font-medium">{r.source_id.slice(0, 8)}…</div>
                    <div className="text-xs text-muted-foreground">{r.started_at}</div>
                  </div>
                  <div className="text-right text-xs">
                    <span className="uppercase tracking-widest">{r.status}</span>
                    <div className="text-muted-foreground">{r.listings_new} new / {r.listings_updated} updated</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title="Latest Open Review Cases" testid="market-recent-cases">
          {cases.length === 0 ? (
            <div className="text-sm text-muted-foreground">No open review cases. Cases are generated automatically once the matcher (Phase B) starts producing probable/possible matches or conflicts.</div>
          ) : (
            <div className="divide-y divide-border text-sm">
              {cases.map((c) => (
                <div key={c.id} className="py-2 flex items-center justify-between" data-testid={`case-row-${c.id}`}>
                  <div className="truncate">
                    <div className="font-medium">{c.case_type}</div>
                    <div className="text-xs text-muted-foreground">{c.id.slice(0, 8)}…</div>
                  </div>
                  <div className="text-right text-xs">
                    <span className="uppercase tracking-widest">{c.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      <div className="mt-4">
        <PhaseBanner phase="Phases B–E">
          Recent activity feed, price-compare trend chart, source health strip and quick-insight donuts (per mockup)
          will populate as the matcher (Phase B), guidance engine (Phase C) and collectors (Phase E) come online.
        </PhaseBanner>
      </div>
    </div>
  );
}
