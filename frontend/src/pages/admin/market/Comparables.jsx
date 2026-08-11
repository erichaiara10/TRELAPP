// 3. Comparable Properties — subject form → live GUIDE-1.0 run → ranked comps.
// Powered by POST /api/admin/market/guidance/run + persisted results.
import React, { useEffect, useState } from "react";
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
                          <tr key={c.id} className="border-b border-border/60" data-testid={`comp-row-${c.id}`}>
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
