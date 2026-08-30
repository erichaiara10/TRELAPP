// 10. Audit Log — read-only feed of every write across market_* collections.
// Backed by /api/admin/market/audit-events (already emitting in Phase 1).
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, KpiCard, Section, LoadError, Pager } from "./_shared";

export default function AuditLog() {
  const [rows, setRows] = useState([]);
  const [entityType, setEntityType] = useState("");
  const [summary, setSummary] = useState({});
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const limit = 100;

  const load = async () => {
    try {
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (entityType) params.set("entity_type", entityType);
      const [{ data }, s] = await Promise.all([api.get(`/admin/market/audit-events?${params}`), api.get("/admin/market/summary")]);
      setRows(data || []); setSummary(s.data || {}); setError("");
    } catch (e) { setError(e?.response?.data?.detail || e?.message || "Audit events could not be loaded."); }
  };
  useEffect(() => { load(); }, [entityType, offset]);

  const entityTypes = ["", "market_source", "collection_run", "source_listing",
                       "master_property", "property_match", "market_review_case",
                       "market_configuration"];

  return (
    <div data-testid="market-audit-page">
      <PageHeader
        title="Audit Log"
        subtitle="Immutable record of every write to the aggregation pipeline — source changes, match decisions, config activations, review resolutions."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KpiCard label="Total Events" value={summary.audit_events} testid="kpi-audit-total" />
        <KpiCard label="Active Config" value={summary.active_config_version} testid="kpi-audit-config" />
        <KpiCard label="Master Properties" value={summary.master_properties} testid="kpi-audit-masters" />
        <KpiCard label="Active Matches" value={summary.matches_active} testid="kpi-audit-matches" />
      </div>

      <div className="mb-3 flex items-center gap-3">
        <label className="text-xs text-muted-foreground">Filter by entity type</label>
        <select value={entityType} onChange={(e) => setEntityType(e.target.value)}
                className="border border-border rounded px-2 py-1 text-sm" data-testid="audit-entity-filter">
          {entityTypes.map((t) => (
            <option key={t || "all"} value={t}>{t || "All"}</option>
          ))}
        </select>
      </div>
      <LoadError message={error} onRetry={load} />

      <Section title={`Events (${rows.length})`} testid="audit-events-table">
        {rows.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">No audit events for this filter.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Timestamp</th>
                  <th className="py-2 pr-3">Event</th>
                  <th className="py-2 pr-3">Entity</th>
                  <th className="py-2 pr-3">Entity ID</th>
                  <th className="py-2 pr-3">Actor</th>
                  <th className="py-2 pr-3">Payload</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id} className="border-b border-border/60 align-top" data-testid={`audit-row-${e.id}`}>
                    <td className="py-2 pr-3 text-xs text-muted-foreground whitespace-nowrap">{e.created_at?.slice(0, 19).replace("T", " ")}</td>
                    <td className="py-2 pr-3 font-medium">{e.event_type}</td>
                    <td className="py-2 pr-3">{e.entity_type || "—"}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{e.entity_id?.slice(0, 8) || "—"}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{e.actor_id?.slice(0, 8) || "system"}</td>
                    <td className="py-2 pr-3 text-xs max-w-md truncate">{JSON.stringify(e.payload || {})}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager offset={offset} limit={limit} count={rows.length} onChange={setOffset} />
      </Section>
    </div>
  );
}
