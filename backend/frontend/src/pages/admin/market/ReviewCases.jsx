// 8. Review Cases — unified admin queue for exceptions across the aggregation
// pipeline: duplicate matches, comparable overrides, source/data-quality, etc.
// Backed by /api/admin/market/review-cases (list + update).
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { PageHeader, KpiCard, Section } from "./_shared";

const TABS = [
  { key: "open", label: "All Open" },
  { key: "in_review", label: "In Review" },
  { key: "resolved", label: "Resolved" },
];

export default function ReviewCases() {
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [selected, setSelected] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/admin/market/review-cases?status=${status}&limit=100`);
    setRows(data || []);
    const s = await api.get("/admin/market/summary");
    setSummary(s.data || {});
  };
  useEffect(() => { load().catch(() => {}); }, [status]);

  const update = async (patch) => {
    if (!selected) return;
    try {
      await api.put(`/admin/market/review-cases/${selected.id}`, patch);
      toast.success("Case updated");
      setSelected(null); load();
    } catch (e) { toast.error(formatError(e)); }
  };

  return (
    <div data-testid="market-review-cases-page">
      <PageHeader
        title="Review Cases"
        subtitle="Central queue for every exception flagged by the aggregation pipeline. Every action is auditable."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KpiCard label="Open Cases" value={summary.review_cases_open} testid="kpi-rc-open" />
        <KpiCard label="Master Properties" value={summary.master_properties} testid="kpi-rc-masters" />
        <KpiCard label="Active Matches" value={summary.matches_active} testid="kpi-rc-matches" />
        <KpiCard label="Audit Events" value={summary.audit_events} testid="kpi-rc-audit" />
      </div>

      <div className="flex gap-2 mb-3" data-testid="review-tabs">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setStatus(t.key)}
                  data-testid={`review-tab-${t.key}`}
                  className={`px-3 py-1.5 text-sm rounded-md border ${status === t.key ? "bg-[#0F172A] text-white border-[#0F172A]" : "border-border bg-white"}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <Section title={`Cases (${rows.length})`} testid="review-cases-table">
            {rows.length === 0 ? (
              <div className="text-sm text-muted-foreground py-6 text-center">No {status.replace("_", " ")} cases.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                    <th className="py-2 pr-3">Case</th>
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">Score</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.id} onClick={() => setSelected(c)}
                        className={`border-b border-border/60 cursor-pointer ${selected?.id === c.id ? "bg-muted/30" : ""}`}
                        data-testid={`review-row-${c.id}`}>
                      <td className="py-2 pr-3 font-mono text-xs">{c.id.slice(0, 8)}</td>
                      <td className="py-2 pr-3">{c.case_type}</td>
                      <td className="py-2 pr-3 tabular-nums">{c.score ?? "—"}</td>
                      <td className="py-2 pr-3 uppercase text-xs tracking-widest">{c.status}</td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">{c.created_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
        </div>

        <div>
          <Section title="Case Detail" testid="review-detail">
            {!selected ? (
              <div className="text-sm text-muted-foreground">Select a case to see full context.</div>
            ) : (
              <div className="space-y-3 text-sm">
                <div><span className="text-xs text-muted-foreground">Case ID</span><div className="font-mono">{selected.id}</div></div>
                <div><span className="text-xs text-muted-foreground">Type</span><div>{selected.case_type}</div></div>
                <div><span className="text-xs text-muted-foreground">Conflicts</span><div>{(selected.conflicts || []).join(", ") || "—"}</div></div>
                <div><span className="text-xs text-muted-foreground">Payload</span>
                  <pre className="mt-1 bg-muted/40 rounded p-2 text-xs overflow-x-auto">{JSON.stringify(selected.payload || {}, null, 2)}</pre>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => update({ status: "in_review" })}
                          className="px-3 py-1.5 text-xs rounded border border-border" data-testid="review-mark-in-review">Mark In Review</button>
                  <button onClick={() => update({ status: "resolved", resolution: "manual_resolved" })}
                          className="px-3 py-1.5 text-xs rounded bg-[#2A5B46] text-white" data-testid="review-resolve">Resolve</button>
                  <button onClick={() => update({ status: "dismissed", resolution: "dismissed" })}
                          className="px-3 py-1.5 text-xs rounded border border-red-300 text-red-700" data-testid="review-dismiss">Dismiss</button>
                </div>
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
