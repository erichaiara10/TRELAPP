// 2. Market Evidence — reads from /api/admin/market/listings.
// Full ranked table + right-panel record inspector will land alongside the
// scrapers in Phase E. For Phase 1 we already surface the empty table so
// the wiring, columns and filters are visible and testable.
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, KpiCard, Section, PhaseBanner } from "./_shared";

export default function MarketEvidence() {
  const [listings, setListings] = useState([]);
  const [summary, setSummary] = useState({});
  useEffect(() => {
    api.get("/admin/market/listings?limit=100").then((r) => setListings(r.data || [])).catch(() => {});
    api.get("/admin/market/summary").then((r) => setSummary(r.data)).catch(() => {});
  }, []);

  return (
    <div data-testid="market-evidence-page">
      <PageHeader
        title="Market Evidence"
        subtitle="Every raw external listing observed by TREL's collectors, deduplicated by source ad ID and linked to the master property identity graph."
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <KpiCard label="Active Evidence" value={summary.active_listings} testid="kpi-evidence-active" />
        <KpiCard label="Total Listings" value={summary.market_listings} testid="kpi-evidence-total" />
        <KpiCard label="Linked to Masters" value={summary.matches_active} testid="kpi-evidence-linked" />
        <KpiCard label="Master Properties" value={summary.master_properties} testid="kpi-evidence-masters" />
        <KpiCard label="Data Sources" value={`${summary.active_sources ?? 0}/${summary.sources ?? 0}`} testid="kpi-evidence-sources" />
      </div>

      <Section title="Active Evidence" testid="market-evidence-table">
        {listings.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">
            No market listings yet. Once a public listing collector is configured (Phase E) and its first run completes,
            deduplicated records will appear here for identity matching.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Record ID</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Purpose</th>
                  <th className="py-2 pr-3">Class</th>
                  <th className="py-2 pr-3">Location</th>
                  <th className="py-2 pr-3">Price</th>
                  <th className="py-2 pr-3">Last Seen</th>
                  <th className="py-2 pr-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {listings.map((l) => (
                  <tr key={l.id} className="border-b border-border/60" data-testid={`evidence-row-${l.id}`}>
                    <td className="py-2 pr-3 font-mono text-xs">{l.id.slice(0, 8)}</td>
                    <td className="py-2 pr-3">{l.source_id?.slice(0, 8)}</td>
                    <td className="py-2 pr-3">{l.purpose}</td>
                    <td className="py-2 pr-3">{l.property_class || "—"}</td>
                    <td className="py-2 pr-3">{[l.suburb, l.city].filter(Boolean).join(", ")}</td>
                    <td className="py-2 pr-3 tabular-nums">{l.price ?? "—"}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{l.last_seen}</td>
                    <td className="py-2 pr-3 uppercase text-xs tracking-widest">{l.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <div className="mt-4">
        <PhaseBanner phase="Phase E">
          Right-panel record inspector (normalized vs raw fields, source URL, recent history) and filter chips per the mockup ship with the first collector rollout.
        </PhaseBanner>
      </div>
    </div>
  );
}
