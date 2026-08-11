// 3. Comparable Properties — subject form → live GUIDE-1.0 run → ranked comps.
// Powered by POST /api/admin/market/guidance/run + persisted results.
import React, { useEffect, useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";
import { toast } from "sonner";
import { api, formatError, money } from "@/lib/api";
import { PageHeader, KpiCard, Section } from "./_shared";

const emptySubject = {
  purpose: "sale",
  property_class: "residential",
  property_subtype: "House",
  suburb: "Gordons",
  street: "",
  local_area: "",
  bedrooms: 3, bathrooms: 2,
  land_area_m2: 600, building_area_m2: 180,
  subject_asking_price: "",
  workflow: "seller",
};

function fmt(v) { return v == null ? "—" : money(v); }

export default function MarketComparables() {
  const [subject, setSubject] = useState(emptySubject);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [comps, setComps] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("included");
  const [detail, setDetail] = useState(null);

  useEffect(() => { loadHistory(); }, []);
  const loadHistory = async () => {
    const { data } = await api.get("/admin/market/guidance/results?limit=10");
    setHistory(data || []);
  };

  const run = async () => {
    setRunning(true); setResult(null); setComps([]);
    try {
      const { data } = await api.post("/admin/market/guidance/run", subject);
      setResult(data.result);
      setComps(data.comparables || []);
      toast.success(`Guidance ready — ${data.result.comparable_count} comparables, ${data.result.confidence_label} confidence`);
      loadHistory();
    } catch (e) { toast.error(formatError(e)); }
    finally { setRunning(false); }
  };

  const openHistory = async (id) => {
    try {
      const { data } = await api.get(`/admin/market/guidance/results/${id}`);
      setResult(data.result); setComps(data.comparables || []);
      if (data.request?.subject_snapshot) setSubject((s) => ({ ...s, ...data.request.subject_snapshot }));
    } catch (e) { toast.error(formatError(e)); }
  };

  const included = comps.filter((c) => c.inclusion_status === "included");
  const outliers = comps.filter((c) => c.inclusion_status === "excluded_outlier");
  const excluded = comps.filter((c) => c.inclusion_status === "excluded_quality");
  const current = tab === "included" ? included : tab === "outliers" ? outliers : excluded;

  return (
    <div data-testid="market-comparables-page">
      <PageHeader
        title="Comparable Properties"
        subtitle="Run the GUIDE-1.0 engine against a subject property and inspect the ranked comparables, quality scores and evidence-based ranges."
      />

      <div className="grid lg:grid-cols-3 gap-4">
        <Section title="Subject Property" testid="comparables-subject-form">
          <div className="grid grid-cols-2 gap-2 text-sm">
            <FieldSelect label="Purpose" value={subject.purpose} testid="purpose"
                         options={["sale", "rent"]}
                         onChange={(v) => setSubject({ ...subject, purpose: v })} />
            <FieldSelect label="Workflow" value={subject.workflow} testid="workflow"
                         options={["seller", "buyer", "landlord", "renter", "admin"]}
                         onChange={(v) => setSubject({ ...subject, workflow: v })} />
            <FieldSelect label="Class" value={subject.property_class} testid="class"
                         options={["residential", "commercial_industrial", "vacant_land"]}
                         onChange={(v) => setSubject({ ...subject, property_class: v })} />
            <FieldText label="Subtype" value={subject.property_subtype} testid="subtype"
                       onChange={(v) => setSubject({ ...subject, property_subtype: v })} />
            <FieldText label="Suburb *" value={subject.suburb} testid="suburb"
                       onChange={(v) => setSubject({ ...subject, suburb: v })} />
            <FieldText label="Street" value={subject.street} testid="street"
                       onChange={(v) => setSubject({ ...subject, street: v })} />
            <FieldText label="Local Area" value={subject.local_area} testid="local-area"
                       onChange={(v) => setSubject({ ...subject, local_area: v })} />
            <FieldNum label="Bedrooms" value={subject.bedrooms} testid="beds"
                      onChange={(v) => setSubject({ ...subject, bedrooms: v })} />
            <FieldNum label="Bathrooms" value={subject.bathrooms} testid="baths"
                      onChange={(v) => setSubject({ ...subject, bathrooms: v })} />
            <FieldNum label="Land area (m²)" value={subject.land_area_m2} testid="land"
                      onChange={(v) => setSubject({ ...subject, land_area_m2: v })} />
            <FieldNum label="Building area (m²)" value={subject.building_area_m2} testid="building"
                      onChange={(v) => setSubject({ ...subject, building_area_m2: v })} />
            <FieldNum label="Asking price" value={subject.subject_asking_price} testid="asking"
                      onChange={(v) => setSubject({ ...subject, subject_asking_price: v })} />
          </div>
          <button onClick={run} disabled={running}
                  className="mt-4 w-full px-3 py-2 rounded bg-[#2A5B46] text-white text-sm disabled:opacity-60"
                  data-testid="run-guidance-btn">
            {running ? "Running…" : "Run Guidance"}
          </button>

          <div className="mt-6">
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Recent runs</div>
            <div className="divide-y divide-border text-sm">
              {history.length === 0 && <div className="text-muted-foreground py-2">No runs yet.</div>}
              {history.map((h) => (
                <button key={h.id} onClick={() => openHistory(h.id)}
                        className="w-full text-left py-2 hover:bg-muted/30 flex items-center justify-between"
                        data-testid={`history-${h.id}`}>
                  <div>
                    <div>{h.outputs?.workflow || "admin"} · {h.comparable_count} comps</div>
                    <div className="text-xs text-muted-foreground">{h.created_at?.slice(0, 16)?.replace("T", " ")}</div>
                  </div>
                  <div className="text-xs uppercase tracking-widest">{h.confidence_label}</div>
                </button>
              ))}
            </div>
          </div>
        </Section>

        <div className="lg:col-span-2">
          {result ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <KpiCard label="Comparables" value={result.comparable_count} testid="kpi-comp-count" />
                <KpiCard label="Weighted median" value={fmt(result.weighted_median)} testid="kpi-comp-wmed" />
                <KpiCard label="TREL indicative"
                         value={result.trel_indicative_range?.p25 ? `${fmt(result.trel_indicative_range.p25)} — ${fmt(result.trel_indicative_range.p75)}` : "—"}
                         testid="kpi-comp-range" />
                <KpiCard label="Confidence"
                         value={`${result.confidence_label} (${result.confidence_score?.toFixed?.(0)})`}
                         testid="kpi-comp-confidence" />
              </div>

              <div className="flex gap-2 mb-3">
                <TabBtn label={`Included (${included.length})`} active={tab === "included"} onClick={() => setTab("included")} testid="tab-included" />
                <TabBtn label={`Outliers (${outliers.length})`} active={tab === "outliers"} onClick={() => setTab("outliers")} testid="tab-outliers" />
                <TabBtn label={`Excluded (${excluded.length})`} active={tab === "excluded"} onClick={() => setTab("excluded")} testid="tab-excluded" />
              </div>

              <Section title="Comparables" testid="comparables-table">
                {current.length === 0 ? (
                  <div className="text-sm text-muted-foreground py-4">No comparables in this tab.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                          <th className="py-2 pr-3">Master</th>
                          <th className="py-2 pr-3">Tier</th>
                          <th className="py-2 pr-3">CQS</th>
                          <th className="py-2 pr-3">Recency</th>
                          <th className="py-2 pr-3">Effective</th>
                          <th className="py-2 pr-3 text-right">Value</th>
                          <th className="py-2 pr-3">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {current.map((c) => (
                          <tr key={c.id}
                              onClick={() => setDetail(c)}
                              className={`border-b border-border/60 cursor-pointer hover:bg-muted/30 ${detail?.id === c.id ? "bg-muted/30" : ""}`}
                              data-testid={`comp-row-${c.id}`}>
                            <td className="py-2 pr-3 font-mono text-xs">{c.master_property_id?.slice(0, 8)}</td>
                            <td className="py-2 pr-3">{c.tier}</td>
                            <td className="py-2 pr-3 tabular-nums">{c.quality_score?.toFixed?.(1)}</td>
                            <td className="py-2 pr-3 tabular-nums">{c.recency_factor?.toFixed?.(2)}</td>
                            <td className="py-2 pr-3 tabular-nums">{c.effective_weight?.toFixed?.(3)}</td>
                            <td className="py-2 pr-3 text-right tabular-nums">{fmt(c.value)}</td>
                            <td className="py-2 pr-3 text-xs uppercase tracking-widest">
                              {c.inclusion_status}{c.exclusion_reason ? ` · ${c.exclusion_reason}` : ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>

              <div className="mt-4 text-xs text-muted-foreground">
                Algorithm {result.algorithm_version} · config {result.config_version}.
                Median {fmt(result.median)} · observed {fmt(result.observed_range?.min)}–{fmt(result.observed_range?.max)}.
              </div>
            </>
          ) : (
            <Section title="Ready" testid="comparables-empty">
              <div className="text-sm text-muted-foreground">
                Fill in a subject property (at least purpose + class + suburb) and click "Run Guidance" to see live comparables, the TREL Indicative Range and a confidence label.
              </div>
            </Section>
          )}
        </div>
      </div>

      {detail && <ComparableDetail comp={detail} subject={subject} onClose={() => setDetail(null)} />}
    </div>
  );
}

const CQS_COLORS = { location: "#2A5B46", class_subtype: "#4B8B70", size: "#7BB593",
                     features: "#B5DAB8", condition: "#F1B24A", recency: "#DC7B3E" };

function ComparableDetail({ comp, subject, onClose }) {
  const breakdown = comp.cqs_breakdown || {};
  const data = Object.entries(breakdown).map(([k, v]) => ({
    signal: k.replace(/_/g, " "), score: Number(v || 0), color: CQS_COLORS[k] || "#6B7280",
  }));
  const [showCompare, setShowCompare] = React.useState(false);
  const snap = comp.snapshot || {};
  const rows = [
    { label: "Suburb",         subj: subject.suburb,              cand: snap.suburb },
    { label: "Property subtype", subj: subject.property_subtype,  cand: snap.property_subtype },
    { label: "Bedrooms",       subj: subject.bedrooms,            cand: snap.bedrooms },
    { label: "Bathrooms",      subj: subject.bathrooms,           cand: snap.bathrooms },
    { label: "Land area (m²)", subj: subject.land_area_m2,        cand: snap.land_area_m2 },
    { label: "Building area (m²)", subj: subject.building_area_m2, cand: snap.building_area_m2 },
    { label: "Street",         subj: subject.street,              cand: snap.street },
    { label: "Local area",     subj: subject.local_area,          cand: snap.local_area },
  ];
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-6"
         onClick={onClose} data-testid="comp-detail-modal">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[85vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Comparable · {comp.tier}</div>
            <div className="text-xl font-semibold mt-1">CQS Breakdown</div>
            <div className="text-sm text-muted-foreground mt-1">
              Master <span className="font-mono">{comp.master_property_id?.slice(0, 8)}</span>
              {" · "}Value <span className="tabular-nums">{money(comp.value)}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"
                  data-testid="comp-detail-close">✕</button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
          <KpiCard label="Total CQS" value={comp.quality_score?.toFixed?.(1)} testid="kpi-cqs" />
          <KpiCard label="Recency factor" value={comp.recency_factor?.toFixed?.(2)} testid="kpi-recency" />
          <KpiCard label="Effective weight" value={comp.effective_weight?.toFixed?.(3)} testid="kpi-eff" />
          <KpiCard label="Months since obs." value={comp.months_since?.toFixed?.(1)} testid="kpi-months" />
        </div>

        <div className="flex items-center gap-3 mb-3">
          <label className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground cursor-pointer"
                 data-testid="toggle-compare-subject">
            <input type="checkbox" checked={showCompare}
                   onChange={(e) => setShowCompare(e.target.checked)}
                   data-testid="input-compare-subject" />
            Compare with subject
          </label>
        </div>

        {showCompare && (
          <div className="mb-4 border border-border rounded overflow-hidden" data-testid="compare-with-subject">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-widest text-muted-foreground">
                <tr>
                  <th className="py-1.5 px-3 text-left">Attribute</th>
                  <th className="py-1.5 px-3 text-left">Subject</th>
                  <th className="py-1.5 px-3 text-left">Comparable</th>
                  <th className="py-1.5 px-3 text-left">Δ</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const a = r.subj == null || r.subj === "" ? null : r.subj;
                  const b = r.cand == null || r.cand === "" ? null : r.cand;
                  let delta = "—", tone = "text-muted-foreground";
                  if (typeof a === "number" && typeof b === "number" && a !== 0) {
                    const pct = ((b - a) / a) * 100;
                    delta = `${pct > 0 ? "+" : ""}${pct.toFixed(0)}%`;
                    tone = Math.abs(pct) <= 10 ? "text-[#2A5B46]" : Math.abs(pct) <= 25 ? "text-amber-600" : "text-red-600";
                  } else if (a != null && b != null && String(a).toLowerCase() !== String(b).toLowerCase()) {
                    delta = "≠"; tone = "text-amber-600";
                  } else if (a != null && b != null) {
                    delta = "="; tone = "text-[#2A5B46]";
                  }
                  return (
                    <tr key={r.label} className="border-t border-border/60"
                        data-testid={`compare-row-${r.label.replace(/\W+/g, "-").toLowerCase()}`}>
                      <td className="py-1.5 px-3 text-muted-foreground">{r.label}</td>
                      <td className="py-1.5 px-3 tabular-nums">{a == null ? "—" : a}</td>
                      <td className="py-1.5 px-3 tabular-nums">{b == null ? "—" : b}</td>
                      <td className={`py-1.5 px-3 text-xs uppercase tracking-widest ${tone}`}>{delta}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {data.length > 0 ? (
          <>
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
              Signal contribution
            </div>
            <div className="h-56" data-testid="cqs-breakdown-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} layout="vertical" margin={{ left: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="signal" tick={{ fontSize: 11 }} width={100} />
                  <Tooltip />
                  <Bar dataKey="score">
                    {data.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="text-xs text-muted-foreground mt-3">
              Each bar shows the CQS points contributed by that signal against the subject
              ({subject.property_class} · {subject.suburb}). Total sums to the CQS above.
            </div>
          </>
        ) : (
          <div className="text-sm text-muted-foreground py-6 text-center">
            No breakdown recorded on this comparable (older guidance run — re-run to capture).
          </div>
        )}

        <div className="mt-5 flex justify-between text-xs text-muted-foreground">
          <span>Status: <strong className="uppercase tracking-widest">{comp.inclusion_status}</strong></span>
          {comp.exclusion_reason && <span>Reason: {comp.exclusion_reason}</span>}
        </div>
      </div>
    </div>
  );
}

function FieldText({ label, value, onChange, testid }) {
  return (
    <label className="block" data-testid={`field-${testid}`}>
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <input value={value ?? ""} onChange={(e) => onChange(e.target.value)}
             className="w-full border border-border rounded px-2 py-1.5 text-sm"
             data-testid={`input-${testid}`} />
    </label>
  );
}
function FieldNum({ label, value, onChange, testid }) {
  return (
    <label className="block" data-testid={`field-${testid}`}>
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <input type="number" value={value ?? ""}
             onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
             className="w-full border border-border rounded px-2 py-1.5 text-sm"
             data-testid={`input-${testid}`} />
    </label>
  );
}
function FieldSelect({ label, value, options, onChange, testid }) {
  return (
    <label className="block" data-testid={`field-${testid}`}>
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <select value={value} onChange={(e) => onChange(e.target.value)}
              className="w-full border border-border rounded px-2 py-1.5 text-sm"
              data-testid={`select-${testid}`}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
function TabBtn({ label, active, onClick, testid }) {
  return (
    <button onClick={onClick} data-testid={testid}
            className={`px-3 py-1.5 text-sm rounded-md border ${active ? "bg-[#0F172A] text-white border-[#0F172A]" : "border-border bg-white"}`}>
      {label}
    </button>
  );
}
