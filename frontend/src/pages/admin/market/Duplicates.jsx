// 6. Duplicate Matches — matcher review queue with per-case signal breakdown.
// Live table reads from /api/admin/market/matches; review cases from
// /api/admin/market/review-cases. Includes a dev "Ingest test listing" util
// so admins can drive the matcher without a scraper.
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { PageHeader, KpiCard, Section, PhaseBanner } from "./_shared";

const TABS = [
  { key: "confirmed", label: "Confirmed Matches" },
  { key: "probable", label: "Probable" },
  { key: "possible", label: "Possible" },
  { key: "conflict", label: "Conflicts" },
];

function bandColor(band) {
  switch (band) {
    case "certain": return "bg-emerald-100 text-emerald-800";
    case "automatic": return "bg-green-100 text-green-800";
    case "probable": return "bg-yellow-100 text-yellow-800";
    case "possible": return "bg-orange-100 text-orange-800";
    case "conflict_review": return "bg-red-100 text-red-800";
    default: return "bg-slate-100 text-slate-800";
  }
}

export default function DuplicateMatches() {
  const [tab, setTab] = useState("confirmed");
  const [summary, setSummary] = useState({});
  const [cases, setCases] = useState([]);
  const [matches, setMatches] = useState([]);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [selectedCase, setSelectedCase] = useState(null);
  const [showIngest, setShowIngest] = useState(false);

  const loadCommon = async () => {
    const s = await api.get("/admin/market/summary"); setSummary(s.data || {});
    const m = await api.get("/admin/market/matches?status=active&limit=100"); setMatches(m.data || []);
  };
  useEffect(() => { loadCommon().catch(() => {}); }, []);

  useEffect(() => {
    if (tab === "confirmed") return;
    api.get(`/admin/market/review-cases?status=open&case_type=${tab}&limit=100`)
      .then((r) => setCases(r.data || [])).catch(() => setCases([]));
  }, [tab]);

  const detachMatch = async (id) => {
    if (!window.confirm("Detach this match? It becomes reversible history.")) return;
    try {
      await api.post(`/admin/market/matches/${id}/detach`, { reason: "manual UI detach" });
      toast.success("Detached"); setSelectedMatch(null); loadCommon();
    } catch (e) { toast.error(formatError(e)); }
  };

  return (
    <div data-testid="market-duplicates-page">
      <PageHeader
        title="Duplicate Matches"
        subtitle="Every listing→master link produced by MATCH-1.0, with the signal breakdown that drove the decision. Detach anything that looks wrong — history is preserved."
        actions={
          <button onClick={() => setShowIngest(true)}
                  className="px-3 py-1.5 rounded border border-border text-sm"
                  data-testid="ingest-test-btn">
            + Ingest Test Listing
          </button>
        }
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

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          {tab === "confirmed" ? (
            <Section title="Confirmed matches" testid="dup-confirmed-section">
              {matches.length === 0 ? (
                <div className="text-sm text-muted-foreground py-6 text-center">No matches yet — use "Ingest Test Listing" to drive the matcher.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                      <th className="py-2 pr-3">Match</th>
                      <th className="py-2 pr-3">Listing</th>
                      <th className="py-2 pr-3">Master</th>
                      <th className="py-2 pr-3">Method</th>
                      <th className="py-2 pr-3">Band</th>
                      <th className="py-2 pr-3 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {matches.map((m) => (
                      <tr key={m.id} onClick={() => { setSelectedMatch(m); setSelectedCase(null); }}
                          className={`border-b border-border/60 cursor-pointer ${selectedMatch?.id === m.id ? "bg-muted/30" : ""}`}
                          data-testid={`match-row-${m.id}`}>
                        <td className="py-2 pr-3 font-mono text-xs">{m.id.slice(0, 8)}</td>
                        <td className="py-2 pr-3 font-mono text-xs">{m.market_listing_id?.slice(0, 8)}</td>
                        <td className="py-2 pr-3 font-mono text-xs">{m.master_property_id?.slice(0, 8) || "—"}</td>
                        <td className="py-2 pr-3">{m.method}</td>
                        <td className="py-2 pr-3">
                          <span className={`text-[10px] px-2 py-0.5 rounded ${bandColor(m.decision_band)}`}>
                            {m.decision_band}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{m.score?.toFixed?.(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>
          ) : (
            <Section title={`${TABS.find((t) => t.key === tab)?.label} queue`} testid={`dup-queue-${tab}`}>
              {cases.length === 0 ? (
                <div className="text-sm text-muted-foreground py-6 text-center">No open {tab} cases.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                      <th className="py-2 pr-3">Case</th>
                      <th className="py-2 pr-3">Score</th>
                      <th className="py-2 pr-3">Listing</th>
                      <th className="py-2 pr-3">Proposed Master</th>
                      <th className="py-2 pr-3">Conflicts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c) => (
                      <tr key={c.id} onClick={() => { setSelectedCase(c); setSelectedMatch(null); }}
                          className={`border-b border-border/60 cursor-pointer ${selectedCase?.id === c.id ? "bg-muted/30" : ""}`}
                          data-testid={`case-row-${c.id}`}>
                        <td className="py-2 pr-3 font-mono text-xs">{c.id.slice(0, 8)}</td>
                        <td className="py-2 pr-3 tabular-nums">{c.score?.toFixed?.(1) ?? "—"}</td>
                        <td className="py-2 pr-3 font-mono text-xs">{c.market_listing_id?.slice(0, 8) || "—"}</td>
                        <td className="py-2 pr-3 font-mono text-xs">{c.proposed_master_property_id?.slice(0, 8) || "—"}</td>
                        <td className="py-2 pr-3 text-xs">{(c.conflicts || []).join(", ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>
          )}
        </div>

        <div>
          <Section title="Detail" testid="dup-detail">
            {!selectedMatch && !selectedCase && (
              <div className="text-sm text-muted-foreground">Select a row to see the signal breakdown.</div>
            )}
            {selectedMatch && <MatchDetail match={selectedMatch} onDetach={() => detachMatch(selectedMatch.id)} />}
            {selectedCase && <CaseDetail c={selectedCase} />}
          </Section>
        </div>
      </div>

      {showIngest && <IngestModal onClose={() => setShowIngest(false)} onDone={() => { setShowIngest(false); loadCommon(); }} />}
    </div>
  );
}

function MatchDetail({ match, onDetach }) {
  const signals = match.signals || {};
  const total = Object.values(signals).reduce((a, b) => (typeof b === "number" ? a + b : a), 0);
  return (
    <div className="text-sm space-y-3" data-testid="match-detail">
      <div>
        <div className="text-xs text-muted-foreground">Match</div>
        <div className="font-mono text-xs">{match.id}</div>
      </div>
      <div>
        <div className="text-xs text-muted-foreground">Method / Band</div>
        <div>{match.method} · {match.decision_band} · score {match.score?.toFixed?.(1)}</div>
      </div>
      <div>
        <div className="text-xs text-muted-foreground">Signal breakdown</div>
        {Object.entries(signals).length === 0 && <div className="text-muted-foreground">—</div>}
        <div className="mt-1 divide-y divide-border">
          {Object.entries(signals).map(([k, v]) => (
            <div key={k} className="py-1 flex items-center justify-between text-xs">
              <span className="capitalize">{k.replace(/_/g, " ")}</span>
              <span className="tabular-nums">{typeof v === "number" ? v.toFixed(1) : JSON.stringify(v)}</span>
            </div>
          ))}
          {typeof total === "number" && total > 0 && (
            <div className="py-1 flex items-center justify-between text-xs font-medium">
              <span>Total</span><span className="tabular-nums">{total.toFixed(1)}</span>
            </div>
          )}
        </div>
      </div>
      {(match.conflicts || []).length > 0 && (
        <div>
          <div className="text-xs text-muted-foreground">Conflicts</div>
          <div className="text-red-700 text-xs">{match.conflicts.join(", ")}</div>
        </div>
      )}
      <div className="text-xs text-muted-foreground">
        {match.algorithm_version} · {match.config_version}
      </div>
      <button onClick={onDetach}
              className="w-full mt-2 px-3 py-1.5 rounded border border-red-300 text-red-700 text-sm"
              data-testid="detach-match-btn">
        Detach match
      </button>
    </div>
  );
}

function CaseDetail({ c }) {
  return (
    <div className="text-sm space-y-3" data-testid="case-detail">
      <div><div className="text-xs text-muted-foreground">Case</div><div className="font-mono text-xs">{c.id}</div></div>
      <div><div className="text-xs text-muted-foreground">Type · Score</div><div>{c.case_type} · {c.score?.toFixed?.(1) ?? "—"}</div></div>
      <div><div className="text-xs text-muted-foreground">Conflicts</div><div className="text-xs">{(c.conflicts || []).join(", ") || "—"}</div></div>
      {c.payload?.signals && (
        <div>
          <div className="text-xs text-muted-foreground">Signal breakdown</div>
          <div className="mt-1 divide-y divide-border">
            {Object.entries(c.payload.signals).map(([k, v]) => (
              <div key={k} className="py-1 flex items-center justify-between text-xs">
                <span className="capitalize">{k.replace(/_/g, " ")}</span>
                <span className="tabular-nums">{typeof v === "number" ? v.toFixed(1) : JSON.stringify(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {c.payload?.other_candidates?.length > 0 && (
        <div>
          <div className="text-xs text-muted-foreground">Other candidates considered</div>
          <div className="text-xs">
            {c.payload.other_candidates.map((o) => (
              <div key={o.master_id}>{o.master_id.slice(0, 8)} · {Number(o.score || 0).toFixed(1)}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function IngestModal({ onClose, onDone }) {
  const [form, setForm] = useState({
    source_id: "src-dev", source_listing_id: `L${Date.now()}`,
    purpose: "sale", price: 850000,
    property_class: "residential", property_subtype: "House",
    lot_number: "10", section_number: "5", street: "Angau Drive", suburb: "Gordons",
    bedrooms: 3, bathrooms: 2, land_area_m2: 600, building_area_m2: 180,
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async () => {
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post("/admin/market/listings", form);
      setResult(data);
      toast.success(data.match ? `Match: ${data.match.method} · ${data.match.decision_band}` :
                    data.review_case ? `Review case: ${data.review_case.case_type}` :
                    "Ingested");
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" data-testid="ingest-modal">
      <div className="bg-white rounded-lg p-5 w-full max-w-2xl">
        <div className="text-lg font-semibold mb-4">Ingest Test Listing</div>
        <div className="grid grid-cols-2 gap-2 text-sm max-h-[400px] overflow-y-auto">
          {Object.entries(form).map(([k, v]) => (
            <label key={k} className="block">
              <div className="text-xs text-muted-foreground mb-1 capitalize">{k.replace(/_/g, " ")}</div>
              <input value={v ?? ""} onChange={(e) => setForm({ ...form, [k]: k.includes("area") || k === "price" || ["bedrooms", "bathrooms"].includes(k) ? (e.target.value === "" ? null : Number(e.target.value)) : e.target.value })}
                     className="w-full border border-border rounded px-2 py-1.5"
                     data-testid={`ingest-${k}`} />
            </label>
          ))}
        </div>

        {result && (
          <div className="mt-4 p-3 bg-muted/40 rounded text-xs font-mono max-h-40 overflow-y-auto">
            <div className="mb-1 font-medium">Result:</div>
            {result.match && <div>Match — {result.match.method} · {result.match.decision_band} · score {result.match.score}</div>}
            {result.review_case && <div>Review case created — {result.review_case.case_type}</div>}
            {result.excluded && <div>Excluded: {result.reason}</div>}
            <div>Candidates considered: {result.candidates_considered}</div>
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm rounded border border-border" data-testid="ingest-close">Close</button>
          <button onClick={submit} disabled={busy}
                  className="px-3 py-1.5 text-sm rounded bg-[#2A5B46] text-white disabled:opacity-60"
                  data-testid="ingest-submit">
            {busy ? "Running…" : "Ingest & Match"}
          </button>
        </div>
      </div>
    </div>
  );
}
