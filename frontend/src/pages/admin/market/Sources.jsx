// 5. Data Sources — full CRUD screen for the market_sources collection.
// Backed by the live Phase 1 endpoints. Includes recent collection runs
// summary (empty until Phase E schedules a scrape).
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { PageHeader, KpiCard, Section } from "./_shared";
import SelectorTester from "./SelectorTester";
import SourceModal from "./SourceModal";

export default function DataSources() {
  const [rows, setRows] = useState([]);
  const [health, setHealth] = useState([]);
  const [runs, setRuns] = useState([]);
  const [summary, setSummary] = useState({});
  const [collectors, setCollectors] = useState([]);
  const [sched, setSched] = useState(null);
  const [editingSource, setEditingSource] = useState(null);           // full row or "new"
  const [testerSource, setTesterSource] = useState(null);

  const load = async () => {
    // Promise.allSettled — a single failing endpoint must NOT blank the whole
    // admin screen. Every widget renders off its own slice; failed slices
    // stay empty.
    const results = await Promise.allSettled([
      api.get("/admin/market/sources"),
      api.get("/admin/market/sources/health"),
      api.get("/admin/market/runs?limit=10"),
      api.get("/admin/market/summary"),
      api.get("/admin/market/collectors"),
      api.get("/admin/market/scheduler"),
    ]);
    const val = (i, fallback) => results[i].status === "fulfilled" ? results[i].value.data : fallback;
    setRows(val(0, [])); setHealth(val(1, [])); setRuns(val(2, []));
    setSummary(val(3, {})); setCollectors(val(4, [])); setSched(val(5, null));
  };
  useEffect(() => { load().catch(() => {}); }, []);

  const healthFor = (sid) => health.find((h) => h.source_id === sid) || {};

  const toggleScheduler = async () => {
    if (!sched) return;
    try {
      const { data } = await api.post("/admin/market/scheduler/pause", { paused: !sched.paused });
      setSched(data);
      toast.success(data.paused ? "Scheduler paused" : "Scheduler resumed");
    } catch (e) { toast.error(formatError(e)); }
  };

  const openNew = () => setEditingSource("new");
  const openEdit = (row) => setEditingSource(row);
  const closeSourceModal = () => setEditingSource(null);
  const handleSaved = () => { closeSourceModal(); load(); };

  const remove = async (row) => {
    if (!window.confirm(`Delete source "${row.name}"? Its listings will remain.`)) return;
    try { await api.delete(`/admin/market/sources/${row.id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(formatError(e)); }
  };

  const triggerRun = async (row) => {
    try {
      toast.info(`Running ${row.collector || "seed"} collector on ${row.name}…`);
      const { data: run } = await api.post(`/admin/market/sources/${row.id}/collect`);
      toast.success(`${row.name}: ${run.status} · ${run.listings_new} new · ${run.matches_created} matches`);
      load();
    } catch (e) { toast.error(formatError(e)); }
  };

  return (
    <div data-testid="market-sources-page">
      <PageHeader
        title="Data Sources"
        subtitle="Configured public listing feeds and internal uploads. Each source has a safety switch for auto-matching."
        actions={
          <div className="flex items-center gap-2">
            {sched && (
              <button onClick={toggleScheduler}
                      className={`px-3 py-1.5 rounded border text-sm ${sched.paused ? "border-amber-400 text-amber-700 bg-amber-50" : "border-emerald-400 text-emerald-700 bg-emerald-50"}`}
                      data-testid="scheduler-toggle-btn">
                Scheduler: {sched.paused ? "Paused — click to resume" : "Running — click to pause"}
              </button>
            )}
            <button onClick={openNew} data-testid="add-source-btn"
                    className="px-3 py-2 rounded-md bg-[#2A5B46] text-white text-sm hover:bg-[#204838]">
              + Add Source
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KpiCard label="Active Sources" value={summary.active_sources} testid="kpi-sources-active" />
        <KpiCard label="Total Sources" value={summary.sources} testid="kpi-sources-total" />
        <KpiCard label="Market Listings" value={summary.market_listings} testid="kpi-sources-listings" />
        <KpiCard label="Active Matches" value={summary.matches_active} testid="kpi-sources-matches" />
      </div>

      <Section title="Sources" testid="sources-table">
        {rows.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">No sources configured. Click "Add Source" to register your first feed.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Name</th>
                  <th className="py-2 pr-3">Frequency</th>
                  <th className="py-2 pr-3">Parser</th>
                  <th className="py-2 pr-3">Active</th>
                  <th className="py-2 pr-3">Success %</th>
                  <th className="py-2 pr-3">Runs</th>
                  <th className="py-2 pr-3">Fail streak</th>
                  <th className="py-2 pr-3">Last run</th>
                  <th className="py-2 pr-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const h = healthFor(r.id);
                  return (
                    <tr key={r.id} className="border-b border-border/60" data-testid={`source-row-${r.id}`}>
                      <td className="py-2 pr-3">
                        <div className="font-medium">{r.name}</div>
                        {r.base_url && <div className="text-xs text-muted-foreground">{r.base_url}</div>}
                      </td>
                      <td className="py-2 pr-3">{r.collection_frequency || "manual"}</td>
                      <td className="py-2 pr-3 text-xs">{r.parser_version || "—"}</td>
                      <td className="py-2 pr-3">{r.active ? "Yes" : "No"}</td>
                      <td className="py-2 pr-3 tabular-nums" data-testid={`health-${r.id}`}>
                        {h.success_rate == null ? "—" : `${h.success_rate}%`}
                      </td>
                      <td className="py-2 pr-3 tabular-nums">{h.runs ?? 0}</td>
                      <td className={`py-2 pr-3 tabular-nums ${h.consecutive_failures > 0 ? "text-red-700" : ""}`}>
                        {h.consecutive_failures ?? 0}
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {(r.last_run_at || "").slice(0, 16).replace("T", " ") || "—"}
                      </td>
                      <td className="py-2 pr-3 text-right whitespace-nowrap">
                        <button onClick={() => triggerRun(r)} data-testid={`run-source-${r.id}`}
                                className="text-xs mr-3 underline">Run</button>
                        {(collectors.find((c) => c.key === r.collector)?.default_config) && (
                          <button onClick={() => setTesterSource(r)}
                                  className="text-xs mr-3 underline"
                                  data-testid={`inspect-source-${r.id}`}>Inspect</button>
                        )}
                        <button onClick={() => openEdit(r)} data-testid={`edit-source-${r.id}`}
                                className="text-xs mr-3 underline">Edit</button>
                        <button onClick={() => remove(r)} data-testid={`delete-source-${r.id}`}
                                className="text-xs text-red-600 underline">Delete</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <div className="mt-4">
        <Section title="Recent Collection Runs" testid="sources-runs">
          {runs.length === 0 ? (
            <div className="text-sm text-muted-foreground">No runs recorded yet. Runs will appear here once a collector (Phase E) executes against any active source.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Run</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Started</th>
                  <th className="py-2 pr-3">New / Updated</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="border-b border-border/60" data-testid={`run-row-${r.id}`}>
                    <td className="py-2 pr-3 font-mono text-xs">{r.id.slice(0, 8)}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{r.source_id.slice(0, 8)}</td>
                    <td className="py-2 pr-3 uppercase text-xs tracking-widest">{r.status}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{r.started_at}</td>
                    <td className="py-2 pr-3">{r.listings_new} / {r.listings_updated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
      </div>

      {editingSource && (
        <SourceModal
          editing={editingSource === "new" ? "new" : editingSource.id}
          initial={editingSource === "new" ? null : editingSource}
          collectors={collectors}
          onClose={closeSourceModal}
          onSaved={handleSaved}
        />
      )}

      {testerSource && (
        <SelectorTester source={testerSource}
                        collectorMeta={collectors.find((c) => c.key === testerSource.collector)}
                        onClose={() => setTesterSource(null)} />
      )}
    </div>
  );
}
