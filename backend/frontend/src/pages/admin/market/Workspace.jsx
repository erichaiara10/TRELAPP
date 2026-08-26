import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { KpiCard, PageHeader, PhaseBanner, Section } from "./_shared";

function useMarketData(path, fallback) {
  const fallbackRef = useRef(fallback);
  const [data, setData] = useState(fallbackRef.current);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.get(path).then((response) => { if (active) setData(response.data ?? fallbackRef.current); })
      .catch(() => { if (active) setError("The live data could not be loaded."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path]);
  return { data, loading, error };
}

const Empty = ({ loading, error, children = "No records are currently available." }) => (
  <div className="text-sm text-muted-foreground py-6 text-center">{loading ? "Loading…" : error || children}</div>
);

export function MarketOverview() {
  const summary = useMarketData("/admin/market/summary", {});
  const s = summary.data || {};
  return <div data-testid="market-overview-page">
    <PageHeader title="Overview" subtitle="Operational summary of aggregated property evidence, source coverage and Master Property matching." />
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
      <KpiCard label="Active Evidence" value={s.active_listings} />
      <KpiCard label="Total Listings" value={s.market_listings} />
      <KpiCard label="Linked to Masters" value={s.matches_active} />
      <KpiCard label="Master Properties" value={s.master_properties} />
      <KpiCard label="Active Sources" value={`${s.active_sources ?? 0}/${s.sources ?? 0}`} />
    </div>
    {summary.error && <Empty error={summary.error} />}
  </div>;
}

export function ComparableProperties() {
  const records = useMarketData("/admin/market/listings?limit=100", []);
  const comparable = useMemo(() => (records.data || []).filter((item) => item.comparable_eligible), [records.data]);
  return <SimpleTablePage title="Comparable Properties" subtitle="Eligible market evidence available for comparable-property analysis." records={comparable} loading={records.loading} error={records.error} />;
}

export function PriceTrends() {
  return <RestoredPage title="Price Trends" phase="Analysis workspace">Price trend results will appear when sufficient dated, deduplicated evidence is available.</RestoredPage>;
}

export function DataSources() {
  const sources = useMarketData("/admin/market/sources", []);
  return <div data-testid="market-data-sources-page">
    <PageHeader title="Data Sources" subtitle="Configured sources that supply external property-market evidence." />
    <Section title="Sources">
      {sources.loading || sources.error || !sources.data.length ? <Empty loading={sources.loading} error={sources.error}>No data sources are configured.</Empty> :
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b"><th className="py-2">Source</th><th>Domain</th><th>Status</th><th>Collector</th></tr></thead><tbody>{sources.data.map((item) => <tr key={item.id} className="border-b border-border/60"><td className="py-2">{item.name}</td><td>{item.domain}</td><td>{item.active === false ? "Inactive" : "Active"}</td><td>{item.collector_key || "—"}</td></tr>)}</tbody></table></div>}
    </Section>
  </div>;
}

export function DuplicateMatches() {
  const reviews = useMarketData("/admin/market/match-reviews", []);
  return <SimpleTablePage title="Duplicate Matches" subtitle="Potential Master Property matches awaiting authorised staff review." records={reviews.data || []} loading={reviews.loading} error={reviews.error} />;
}

export function PriceCompareResults() {
  return <RestoredPage title="Price Compare Results" phase="Results workspace">Buyer, seller and rental comparison results are retained here when a price comparison is completed.</RestoredPage>;
}

export function ReviewCases() {
  const reviews = useMarketData("/admin/market/match-reviews", []);
  return <SimpleTablePage title="Review Cases" subtitle="Open duplicate, comparable override and data-quality exceptions requiring staff review." records={reviews.data || []} loading={reviews.loading} error={reviews.error} />;
}

export function MarketConfiguration() {
  return <RestoredPage title="Configuration" phase="Controlled settings">Property-data matching thresholds and collection rules remain protected configuration.</RestoredPage>;
}

export function MarketAuditLog() {
  return <RestoredPage title="Audit Log" phase="Audit workspace">Property-data collection, matching and review decisions are retained for operational audit.</RestoredPage>;
}

function RestoredPage({ title, phase, children }) {
  const testId = `market-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-page`;
  return <div data-testid={testId}><PageHeader title={title} /><PhaseBanner phase={phase}>{children}</PhaseBanner></div>;
}

function SimpleTablePage({ title, subtitle, records, loading, error }) {
  return <div data-testid={`market-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-page`}>
    <PageHeader title={title} subtitle={subtitle} />
    <Section title={title}>
      {loading || error || !records.length ? <Empty loading={loading} error={error} /> :
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b"><th className="py-2">Record</th><th>Property / Source</th><th>Status</th><th>Match</th></tr></thead><tbody>{records.map((item, index) => <tr key={item.id || index} className="border-b border-border/60"><td className="py-2 font-mono text-xs">{item.id || item.source_listing_id || "—"}</td><td>{item.title || item.property_type_name || item.source_name || "—"}</td><td>{item.status || item.current_status || "—"}</td><td>{item.match_status || item.match_rule || "—"}</td></tr>)}</tbody></table></div>}
    </Section>
  </div>;
}
