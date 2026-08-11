// 5. Data Sources — full CRUD screen for the market_sources collection.
// Backed by the live Phase 1 endpoints. Includes recent collection runs
// summary (empty until Phase E schedules a scrape).
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { PageHeader, KpiCard, Section } from "./_shared";

const emptyForm = { name: "", base_url: "", description: "", allow_source_auto_match: true, active: true };

export default function DataSources() {
  const [rows, setRows] = useState([]);
  const [runs, setRuns] = useState([]);
  const [summary, setSummary] = useState({});
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const [{ data: srcs }, { data: rr }, { data: s }] = await Promise.all([
      api.get("/admin/market/sources"),
      api.get("/admin/market/runs?limit=10"),
      api.get("/admin/market/summary"),
    ]);
    setRows(srcs || []); setRuns(rr || []); setSummary(s || {});
  };
  useEffect(() => { load().catch(() => {}); }, []);

  const openNew = () => { setEditing("new"); setForm(emptyForm); };
  const openEdit = (row) => {
    setEditing(row.id);
    setForm({
      name: row.name || "", base_url: row.base_url || "", description: row.description || "",
      allow_source_auto_match: !!row.allow_source_auto_match, active: !!row.active,
    });
  };
  const close = () => { setEditing(null); setForm(emptyForm); };

  const save = async () => {
    try {
      if (editing === "new") await api.post("/admin/market/sources", form);
      else await api.put(`/admin/market/sources/${editing}`, form);
      toast.success("Source saved");
      close(); load();
    } catch (e) { toast.error(formatError(e)); }
  };
  const remove = async (row) => {
    if (!window.confirm(`Delete source "${row.name}"? Its listings will remain.`)) return;
    try { await api.delete(`/admin/market/sources/${row.id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(formatError(e)); }
  };

  return (
    <div data-testid="market-sources-page">
      <PageHeader
        title="Data Sources"
        subtitle="Configured public listing feeds and internal uploads. Each source has a safety switch for auto-matching."
        actions={
          <button onClick={openNew} data-testid="add-source-btn"
                  className="px-3 py-2 rounded-md bg-[#2A5B46] text-white text-sm hover:bg-[#204838]">
            + Add Source
          </button>
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
                  <th className="py-2 pr-3">Base URL</th>
                  <th className="py-2 pr-3">Active</th>
                  <th className="py-2 pr-3">Auto-Match</th>
                  <th className="py-2 pr-3">Created</th>
                  <th className="py-2 pr-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-border/60" data-testid={`source-row-${r.id}`}>
                    <td className="py-2 pr-3 font-medium">{r.name}</td>
                    <td className="py-2 pr-3 text-xs">{r.base_url || "—"}</td>
                    <td className="py-2 pr-3">{r.active ? "Yes" : "No"}</td>
                    <td className="py-2 pr-3">{r.allow_source_auto_match ? "Yes" : "No"}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{r.created_at?.slice(0, 10)}</td>
                    <td className="py-2 pr-3 text-right">
                      <button onClick={() => openEdit(r)} data-testid={`edit-source-${r.id}`}
                              className="text-xs mr-3 underline">Edit</button>
                      <button onClick={() => remove(r)} data-testid={`delete-source-${r.id}`}
                              className="text-xs text-red-600 underline">Delete</button>
                    </td>
                  </tr>
                ))}
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

      {editing && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" data-testid="source-modal">
          <div className="bg-white rounded-lg p-5 w-full max-w-lg">
            <div className="text-lg font-semibold mb-4">{editing === "new" ? "Add Source" : "Edit Source"}</div>
            <div className="space-y-3 text-sm">
              <Field label="Name *" testid="source-name">
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                       className="w-full border border-border rounded px-2 py-1.5" data-testid="input-source-name" />
              </Field>
              <Field label="Base URL" testid="source-url">
                <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                       className="w-full border border-border rounded px-2 py-1.5" data-testid="input-source-url" />
              </Field>
              <Field label="Description" testid="source-desc">
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                          rows={3} className="w-full border border-border rounded px-2 py-1.5" data-testid="input-source-desc" />
              </Field>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2" data-testid="toggle-source-active">
                  <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} /> Active
                </label>
                <label className="flex items-center gap-2" data-testid="toggle-source-automatch">
                  <input type="checkbox" checked={form.allow_source_auto_match}
                         onChange={(e) => setForm({ ...form, allow_source_auto_match: e.target.checked })} /> Allow auto-match
                </label>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={close} className="px-3 py-1.5 text-sm rounded border border-border" data-testid="cancel-source">Cancel</button>
              <button onClick={save} className="px-3 py-1.5 text-sm rounded bg-[#2A5B46] text-white" data-testid="save-source">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children, testid }) {
  return (
    <div data-testid={`field-${testid}`}>
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      {children}
    </div>
  );
}
