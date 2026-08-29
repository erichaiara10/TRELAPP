// BulkRediscoverModal — a top-of-page action that re-runs Discover Pages
// for every HTTP source at once and shows a per-source diff. Ops can spot
// which sites changed their navigation and apply the new URLs one-click.
//
// Nothing is persisted until the operator clicks Apply on a row (or
// Apply All). The scraper continues to use the previously-saved
// listing_pages until then, so this is safe to run any time.
import React, { useMemo, useState } from "react";
import { toast } from "sonner";
import { AlertCircle, CheckCircle2, ChevronDown, ChevronRight,
         MinusCircle, PlusCircle, RefreshCw, X } from "lucide-react";
import { api, formatError } from "@/lib/api";

export default function BulkRediscoverModal({ onClose, onApplied }) {
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [applying, setApplying] = useState({});     // {source_id: bool}

  const run = async () => {
    setBusy(true); setReport(null);
    try {
      const { data } = await api.post("/admin/market/sources/rediscover-all");
      setReport(data);
      const changes = data.with_changes || 0;
      if (changes === 0) {
        toast.success(`Scan complete — no changes across ${data.total} sources`);
      } else {
        toast.info(`Scan complete — ${changes} source${changes === 1 ? "" : "s"} changed`);
      }
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  const applyOne = async (diff) => {
    // Apply = replace the source's listing_pages with the newly-suggested set.
    setApplying((s) => ({ ...s, [diff.source_id]: true }));
    try {
      const pages = (diff.suggested || []).map((c) => ({
        category:       c.category,
        category_label: c.category_label,
        purpose:        c.purpose,
        listing_url:    c.listing_url,
        cards_found:    c.cards_found,
        detail_links:   c.detail_links,
      }));
      await api.put(`/admin/market/sources/${diff.source_id}/listing-pages`,
                    { listing_pages: pages });
      toast.success(`${diff.source_name}: ${pages.length} URL${pages.length === 1 ? "" : "s"} saved`);
      // Locally mark this row as unchanged so the button disappears.
      setReport((r) => ({
        ...r,
        diffs: r.diffs.map((d) => d.source_id === diff.source_id
          ? { ...d, added: [], removed: [], unchanged: pages.map((p) => p.listing_url), before: pages }
          : d),
        with_changes: Math.max(0, (r.with_changes || 1) - 1),
      }));
      onApplied?.();
    } catch (e) { toast.error(formatError(e)); }
    finally {
      setApplying((s) => { const { [diff.source_id]: _drop, ...rest } = s; return rest; });
    }
  };

  const applyAll = async () => {
    if (!report?.diffs) return;
    const targets = report.diffs.filter((d) => d.ok && (d.added.length || d.removed.length));
    if (!targets.length) return;
    for (const d of targets) {
      // Serial so toasts read in a natural order + backend stays polite.
      // eslint-disable-next-line no-await-in-loop
      await applyOne(d);
    }
  };

  const sorted = useMemo(() => {
    if (!report?.diffs) return [];
    // Show changed first, then errors, then unchanged, then skipped
    const score = (d) => {
      if (!d.ok && !d.skipped) return 1;                    // errored
      if (d.skipped) return 4;
      if (d.added.length || d.removed.length) return 0;    // changed
      return 3;                                             // unchanged
    };
    return [...report.diffs].sort((a, b) => score(a) - score(b));
  }, [report]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4 overflow-y-auto"
         onClick={onClose} data-testid="bulk-rediscover-modal">
      <div className="bg-white rounded-lg w-full max-w-5xl my-6" onClick={(e) => e.stopPropagation()}>
        <div className="p-5 border-b border-border flex items-center justify-between">
          <div>
            <div className="text-xl font-semibold flex items-center gap-2">
              <RefreshCw className="w-5 h-5 text-[#2A5B46]" /> Bulk Rediscover
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              Re-scans every HTTP source homepage and shows what changed. Nothing is saved until you Apply.
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"
                  data-testid="bulk-rediscover-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {!report && (
          <div className="p-8 text-center">
            <button onClick={run} disabled={busy}
                    className="px-5 py-2.5 rounded bg-[#2A5B46] text-white text-sm hover:bg-[#204838] disabled:opacity-60 flex items-center gap-2 mx-auto"
                    data-testid="bulk-rediscover-run">
              <RefreshCw className={`w-4 h-4 ${busy ? "animate-spin" : ""}`} />
              {busy ? "Scanning all sources…" : "Run scan"}
            </button>
            <div className="text-xs text-muted-foreground mt-3">
              This can take 30–90 seconds for a full catalogue.
            </div>
          </div>
        )}

        {report && (
          <>
            <div className="p-4 border-b border-border grid grid-cols-5 gap-3 text-sm">
              <SummaryPill label="Total"      value={report.total}       tone="neutral"  testid="sum-total" />
              <SummaryPill label="Changed"    value={report.with_changes} tone="amber"    testid="sum-changed" />
              <SummaryPill label="No changes" value={report.no_changes}   tone="ok"       testid="sum-nochange" />
              <SummaryPill label="Errors"     value={report.errored}      tone="err"      testid="sum-errored" />
              <SummaryPill label="Skipped"    value={report.skipped}      tone="neutral"  testid="sum-skipped" />
            </div>
            <div className="max-h-[55vh] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#FAFBFA] sticky top-0">
                  <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="py-2 pl-4 pr-2 w-8"></th>
                    <th className="py-2 pr-3">Source</th>
                    <th className="py-2 pr-3">Base URL</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3 text-right">Added</th>
                    <th className="py-2 pr-3 text-right">Removed</th>
                    <th className="py-2 pr-3 text-right">Unchanged</th>
                    <th className="py-2 pr-3 text-right pr-4">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((d) => {
                    const changed = d.added.length + d.removed.length;
                    const isOpen = !!expanded[d.source_id];
                    const rowStatus = d.skipped ? "skipped"
                                    : !d.ok ? "error"
                                    : changed ? "changed"
                                    : "same";
                    return (
                      <React.Fragment key={d.source_id}>
                        <tr className="border-t border-border/60"
                            data-testid={`rediscover-row-${d.source_id}`}>
                          <td className="py-2 pl-4 pr-2">
                            {(d.added.length || d.removed.length || d.candidates?.length) ? (
                              <button onClick={() => setExpanded((s) => ({ ...s, [d.source_id]: !s[d.source_id] }))}
                                      className="text-muted-foreground hover:text-foreground"
                                      data-testid={`rediscover-toggle-${d.source_id}`}>
                                {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                              </button>
                            ) : null}
                          </td>
                          <td className="py-2 pr-3 font-medium">{d.source_name}</td>
                          <td className="py-2 pr-3 text-xs text-muted-foreground truncate max-w-[220px]">{d.base_url || "—"}</td>
                          <td className="py-2 pr-3">
                            <StatusPill status={rowStatus} error={d.error} reason={d.reason} />
                          </td>
                          <td className="py-2 pr-3 text-right tabular-nums text-emerald-700">
                            {d.added.length ? `+${d.added.length}` : "0"}
                          </td>
                          <td className="py-2 pr-3 text-right tabular-nums text-red-700">
                            {d.removed.length ? `−${d.removed.length}` : "0"}
                          </td>
                          <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground">{d.unchanged.length}</td>
                          <td className="py-2 pr-3 pr-4 text-right">
                            {rowStatus === "changed" && (
                              <button onClick={() => applyOne(d)}
                                      disabled={applying[d.source_id]}
                                      className="text-xs px-3 py-1 rounded bg-[#2A5B46] text-white hover:bg-[#204838] disabled:opacity-60"
                                      data-testid={`rediscover-apply-${d.source_id}`}>
                                {applying[d.source_id] ? "Applying…" : "Apply"}
                              </button>
                            )}
                          </td>
                        </tr>
                        {isOpen && (
                          <tr>
                            <td colSpan={8} className="bg-[#FAFBFA] px-4 py-3" data-testid={`rediscover-detail-${d.source_id}`}>
                              <DiffDetail diff={d} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="p-4 border-t border-border flex items-center justify-between bg-[#FAFBFA] rounded-b-lg">
              <div className="text-xs text-muted-foreground">
                Sources are re-scanned live. The scraper uses previously-saved URLs until you click Apply.
              </div>
              <div className="flex gap-2">
                <button onClick={run} disabled={busy}
                        className="text-xs px-3 py-1.5 rounded border border-border hover:bg-white"
                        data-testid="bulk-rediscover-rerun">
                  Re-run scan
                </button>
                <button onClick={applyAll}
                        disabled={!(report.with_changes > 0) || busy}
                        className="text-xs px-3 py-1.5 rounded bg-[#2A5B46] text-white hover:bg-[#204838] disabled:opacity-40"
                        data-testid="bulk-rediscover-apply-all">
                  Apply all changed ({report.with_changes})
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SummaryPill({ label, value, tone, testid }) {
  const cls = {
    neutral: "bg-muted/40 text-foreground",
    ok: "bg-[#E7F1EB] text-[#1F5A3C]",
    amber: "bg-amber-50 text-amber-700",
    err: "bg-red-50 text-red-700",
  }[tone] || "bg-muted/40";
  return (
    <div className={`${cls} rounded px-3 py-2`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-widest opacity-80">{label}</div>
      <div className="text-xl font-semibold tabular-nums">{value ?? 0}</div>
    </div>
  );
}

function StatusPill({ status, error, reason }) {
  if (status === "error") return (
    <div className="inline-flex items-center gap-1 text-xs text-red-700 bg-red-50 px-2 py-0.5 rounded"
         title={error || ""}>
      <AlertCircle className="w-3 h-3" /> Error
    </div>
  );
  if (status === "skipped") return (
    <div className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-muted/40 px-2 py-0.5 rounded"
         title={reason || ""}>
      Skipped
    </div>
  );
  if (status === "changed") return (
    <div className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
      Changed
    </div>
  );
  return (
    <div className="inline-flex items-center gap-1 text-xs text-[#1F5A3C] bg-[#E7F1EB] px-2 py-0.5 rounded">
      <CheckCircle2 className="w-3 h-3" /> Unchanged
    </div>
  );
}

function DiffDetail({ diff }) {
  if (diff.error) {
    return (
      <div className="text-xs text-red-700">
        <div className="font-medium mb-1">Rediscovery failed</div>
        <div className="font-mono break-all">{diff.error}</div>
      </div>
    );
  }
  if (diff.skipped) {
    return <div className="text-xs text-muted-foreground">{diff.reason || "Skipped."}</div>;
  }
  return (
    <div className="space-y-3 text-xs">
      {diff.added.length > 0 && (
        <UrlList title="Added" icon={PlusCircle} tone="emerald"
                 urls={diff.added} candidates={diff.suggested || []} testid="added" />
      )}
      {diff.removed.length > 0 && (
        <UrlList title="Removed" icon={MinusCircle} tone="red"
                 urls={diff.removed} candidates={diff.before || []} testid="removed" />
      )}
      {diff.unchanged.length > 0 && (
        <UrlList title="Unchanged" icon={CheckCircle2} tone="muted"
                 urls={diff.unchanged} candidates={diff.suggested || []} testid="unchanged" />
      )}
      {!diff.added.length && !diff.removed.length && !diff.unchanged.length && (
        <div className="text-muted-foreground">No candidates match the auto-confirm threshold on this scan.</div>
      )}
    </div>
  );
}

function UrlList({ title, icon: Icon, tone, urls, candidates, testid }) {
  const toneCls = {
    emerald: "text-emerald-700",
    red: "text-red-700",
    muted: "text-muted-foreground",
  }[tone] || "text-foreground";
  const findMeta = (u) => candidates.find((c) => c.listing_url === u);
  return (
    <div data-testid={`diff-${testid}`}>
      <div className={`font-medium ${toneCls} mb-1 flex items-center gap-1`}>
        <Icon className="w-3 h-3" /> {title} ({urls.length})
      </div>
      <ul className="space-y-0.5 pl-4">
        {urls.map((u) => {
          const meta = findMeta(u);
          return (
            <li key={u} className="flex flex-wrap items-center gap-x-2">
              <span className="font-mono break-all">{u}</span>
              {meta?.category_label && (
                <span className="text-muted-foreground">· {meta.category_label}</span>
              )}
              {typeof meta?.cards_found === "number" && (
                <span className="text-muted-foreground">· {meta.cards_found} cards</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
