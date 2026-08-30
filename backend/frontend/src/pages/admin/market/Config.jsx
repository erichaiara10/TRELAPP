// 9. Configuration — proper tabbed UI with sliders + numeric inputs +
// weight tables (per mockup). Every save creates a new version and
// activates it, so all changes are audit-trailed and reversible.
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { PageHeader, Section } from "./_shared";
const RETENTION_DEFAULTS = {
  raw_source_data_days: 365,
  normalized_data_days: 730,
  review_case_days: 365,
  audit_log_days: 2555,
  soft_delete_only: true,
};
const HEALTH_LED_DEFAULTS = {
  amber_min_success_pct: 90,
  red_consecutive_failures: 2,
};
const DEFAULT_PARAMETERS = {
  certain_min_score: 95, auto_match_threshold: 85, probable_threshold: 70, possible_threshold: 50,
  exact_gps_support_m: 20, exact_gps_conflict_m: 150,
  land_close_tolerance_pct: 10, land_broad_tolerance_pct: 25, building_close_tolerance_pct: 15,
  signal_weights: { gps: 30, lot_section: 25, address: 20, name: 10, land_size: 10, building_size: 5 },
  unit_weights: { building: 30, unit: 30, address: 20, gps: 20 },
  location_same_street_factor: 1, location_same_local_area_factor: 0.85, location_same_suburb_factor: 0.7,
  recency_0_6_factor: 1, recency_7_12_factor: 0.85, recency_13_24_factor: 0.65,
  current_months: 6, relevant_months: 12, historical_support_months: 24,
  quality_min_usable: 40, quality_reasonable_min: 60, quality_close_min: 80,
  size_similarity_bands: { close: 10, reasonable: 25, broad: 50 },
  min_direct_for_formal_range: 3, limited_max_count: 2, moderate_max_count: 5, strong_min_count: 6,
  iqr_outlier_multiplier: 1.5, indicative_lower_percentile: 25, indicative_upper_percentile: 75,
  confidence_weights: { evidence_count: 35, similarity: 35, recency: 20, quality: 10 },
  cqs_baseline: 60, retention: RETENTION_DEFAULTS, health_led: HEALTH_LED_DEFAULTS,
};

const TABS = [
  { key: "duplicate", label: "Duplicate Matching" },
  { key: "comparable", label: "Comparable Selection" },
  { key: "guidance", label: "Price Guidance" },
  { key: "cqs", label: "CQS Baseline" },
  { key: "retention", label: "Data Retention" },
  { key: "advanced", label: "Advanced JSON" },
];

function NumInput({ label, value, onChange, step = 1, min = 0, max, hint, testid }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5" data-testid={`field-${testid}`}>
      <div>
        <div className="text-sm">{label}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </div>
      <input type="number" value={value ?? ""} step={step} min={min} max={max}
             onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
             className="w-28 border border-border rounded px-2 py-1 text-sm text-right tabular-nums"
             data-testid={`input-${testid}`} />
    </div>
  );
}

function Slider({ label, value, onChange, min, max, step = 1, hint, testid }) {
  return (
    <div className="py-2" data-testid={`slider-${testid}`}>
      <div className="flex items-center justify-between mb-1">
        <div className="text-sm">{label}</div>
        <div className="text-sm tabular-nums font-medium">{value}</div>
      </div>
      {hint && <div className="text-xs text-muted-foreground mb-1">{hint}</div>}
      <input type="range" value={value} min={min} max={max} step={step}
             onChange={(e) => onChange(Number(e.target.value))}
             className="w-full" data-testid={`range-${testid}`} />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  );
}

function WeightsTable({ title, weights, onChange, hint, testid }) {
  return (
    <div className="mt-3" data-testid={`weights-${testid}`}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground mb-1">{title}</div>
      {hint && <div className="text-xs text-muted-foreground mb-2">{hint}</div>}
      <div className="bg-muted/30 rounded p-3 divide-y divide-border">
        {Object.entries(weights).map(([k, v]) => (
          <div key={k} className="py-1.5 flex items-center justify-between text-sm">
            <span className="capitalize">{k.replace(/_/g, " ")}</span>
            <input type="number" value={v} min={0} step={1}
                   onChange={(e) => onChange({ ...weights, [k]: Number(e.target.value) })}
                   className="w-20 border border-border rounded px-2 py-1 text-right tabular-nums"
                   data-testid={`weight-${testid}-${k}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MarketConfig() {
  const [tab, setTab] = useState("duplicate");
  const [versions, setVersions] = useState([]);
  const [active, setActive] = useState(null);
  const [params, setParams] = useState(null);       // working copy (edited)
  const [nextVersion, setNextVersion] = useState("");
  const [retentionPreview, setRetentionPreview] = useState(null);
  const [retentionBusy, setRetentionBusy] = useState(false);

  const load = async () => {
    const [{ data: list }, { data: a }] = await Promise.all([
      api.get("/admin/market/config"),
      api.get("/admin/market/config/active?algorithm=combined").catch(() => ({ data: null })),
    ]);
    setVersions(list || []);
    setActive(a?.active ? a : null);
    const p = JSON.parse(JSON.stringify(a?.parameters || DEFAULT_PARAMETERS));
    p.retention = { ...RETENTION_DEFAULTS, ...(p.retention || {}) };
    p.health_led = { ...HEALTH_LED_DEFAULTS, ...(p.health_led || {}) };
    setParams(p);
  };
  useEffect(() => {
    load().catch((e) => {
      toast.error(`Configuration could not be loaded: ${formatError(e)}`);
      setParams(JSON.parse(JSON.stringify(DEFAULT_PARAMETERS)));
    });
  }, []);

  const patch = (k, v) => setParams((p) => ({ ...p, [k]: v }));
  const patchNested = (parent, key, v) => setParams((p) => ({ ...p, [parent]: { ...(p[parent] || {}), [key]: v } }));

  const activate = async (id) => {
    try { await api.post(`/admin/market/config/${id}/activate`); toast.success("Activated"); load(); }
    catch (e) { toast.error(formatError(e)); }
  };

  const doRetentionPreview = async () => {
    setRetentionBusy(true);
    try {
      const { data } = await api.get("/admin/market/retention/preview");
      setRetentionPreview(data);
    } catch (e) { toast.error(formatError(e)); }
    finally { setRetentionBusy(false); }
  };

  const runRetentionNow = async () => {
    if (!window.confirm("Run the retention policy now? Rows past their retention window will be soft-deleted (or hard-deleted if 'Soft delete only' is off).")) return;
    setRetentionBusy(true);
    try {
      const { data } = await api.post("/admin/market/retention/run");
      setRetentionPreview({ ...data, ran: true });
      toast.success("Retention run complete");
    } catch (e) { toast.error(formatError(e)); }
    finally { setRetentionBusy(false); }
  };


  const publish = async () => {
    if (!nextVersion.trim()) { toast.error("Version name required (e.g. COMBINED-1.1)"); return; }
    try {
      await api.post("/admin/market/config", {
        version: nextVersion.trim(), algorithm: "combined",
        parameters: params, notes: "Edited via config sliders", activate: true,
      });
      toast.success(`Published ${nextVersion}`);
      setNextVersion(""); load();
    } catch (e) { toast.error(formatError(e)); }
  };

  if (!params) {
    return (
      <div data-testid="market-config-page">
        <PageHeader title="Configuration" />
        <div className="text-sm text-muted-foreground">Loading…</div>
      </div>
    );
  }

  return (
    <div data-testid="market-config-page">
      <PageHeader
        title="Configuration"
        subtitle={
          active
            ? `Editing from active version ${active.version}. Publishing saves as a new version and activates immediately — every change is audit-trailed and reversible.`
            : "No active configuration."
        }
        actions={
          <div className="flex items-center gap-2">
            <input value={nextVersion} onChange={(e) => setNextVersion(e.target.value)}
                   placeholder="COMBINED-1.1"
                   className="border border-border rounded px-2 py-1.5 text-sm w-40"
                   data-testid="input-next-version" />
            <button onClick={publish}
                    className="px-3 py-1.5 rounded bg-[#2A5B46] text-white text-sm"
                    data-testid="publish-config-btn">
              Publish New Version
            </button>
          </div>
        }
      />

      <div className="grid lg:grid-cols-4 gap-4">
        <div>
          <Section title="Versions" testid="config-versions">
            <div className="divide-y divide-border">
              {versions.map((v) => (
                <div key={v.id} className="py-2 flex items-center justify-between" data-testid={`config-version-${v.version}`}>
                  <div>
                    <div className="font-medium text-sm">{v.version}</div>
                    <div className="text-xs text-muted-foreground">{v.active ? "active" : v.algorithm}</div>
                  </div>
                  {!v.active && (
                    <button onClick={() => activate(v.id)} className="text-xs underline"
                            data-testid={`activate-${v.version}`}>Activate</button>
                  )}
                </div>
              ))}
            </div>
          </Section>
        </div>

        <div className="lg:col-span-3">
          <div className="flex gap-2 mb-3 flex-wrap" data-testid="config-tabs">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                      data-testid={`config-tab-${t.key}`}
                      className={`px-3 py-1.5 text-sm rounded-md border ${tab === t.key ? "bg-[#0F172A] text-white border-[#0F172A]" : "border-border bg-white"}`}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === "duplicate" && (
            <Section title="MATCH-1.0 — Duplicate Matching Rules" testid="config-duplicate">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Decision-band thresholds</div>
                  <Slider label="Certain match (deterministic)" value={params.certain_min_score}
                          min={80} max={100} testid="certain-min"
                          onChange={(v) => patch("certain_min_score", v)}
                          hint="Score gate applied ON TOP of a deterministic rule (D1–D6)." />
                  <Slider label="Automatic match (weighted)" value={params.auto_match_threshold}
                          min={70} max={100} testid="auto-threshold"
                          onChange={(v) => patch("auto_match_threshold", v)}
                          hint="Weighted score at/above this auto-attaches listing→master with no review." />
                  <Slider label="Probable match" value={params.probable_threshold}
                          min={50} max={95} testid="probable-threshold"
                          onChange={(v) => patch("probable_threshold", v)}
                          hint="Goes to review queue as 'probable'." />
                  <Slider label="Possible match" value={params.possible_threshold}
                          min={30} max={80} testid="possible-threshold"
                          onChange={(v) => patch("possible_threshold", v)}
                          hint="Goes to review queue as 'possible'. Below this → new master minted." />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">GPS + size tolerances</div>
                  <NumInput label="Exact-GPS support radius (m)" value={params.exact_gps_support_m}
                            onChange={(v) => patch("exact_gps_support_m", v)} testid="gps-support" />
                  <NumInput label="Hard-conflict radius (m)" value={params.exact_gps_conflict_m}
                            onChange={(v) => patch("exact_gps_conflict_m", v)} testid="gps-conflict" />
                  <NumInput label="Land close tolerance (%)" value={params.land_close_tolerance_pct}
                            onChange={(v) => patch("land_close_tolerance_pct", v)} testid="land-close" />
                  <NumInput label="Land broad tolerance (%)" value={params.land_broad_tolerance_pct}
                            onChange={(v) => patch("land_broad_tolerance_pct", v)} testid="land-broad" />
                  <NumInput label="Building close tolerance (%)" value={params.building_close_tolerance_pct}
                            onChange={(v) => patch("building_close_tolerance_pct", v)} testid="bldg-close" />
                </div>
              </div>

              <WeightsTable title="Positive signal weights (baseline urban parcel — total ≈ 100)"
                            weights={params.signal_weights} testid="signal"
                            hint="Baseline weight applied when the signal matches exactly. Size signals scale by a similarity band."
                            onChange={(w) => patch("signal_weights", w)} />
              <WeightsTable title="Unit / premises weights"
                            weights={params.unit_weights} testid="unit"
                            hint="Applied when the subject is a unit inside a multi-tenancy building."
                            onChange={(w) => patch("unit_weights", w)} />
            </Section>
          )}

          {tab === "comparable" && (
            <Section title="GUIDE-1.0 — Comparable Selection Rules" testid="config-comparable">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Location tier factors</div>
                  <Slider label="Same street" value={params.location_same_street_factor}
                          min={0.5} max={1} step={0.05} testid="loc-street"
                          onChange={(v) => patch("location_same_street_factor", v)} />
                  <Slider label="Same local area / estate" value={params.location_same_local_area_factor}
                          min={0.5} max={1} step={0.05} testid="loc-local"
                          onChange={(v) => patch("location_same_local_area_factor", v)} />
                  <Slider label="Same suburb" value={params.location_same_suburb_factor}
                          min={0.3} max={1} step={0.05} testid="loc-suburb"
                          onChange={(v) => patch("location_same_suburb_factor", v)} />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Recency factors</div>
                  <Slider label="0–6 months (current)" value={params.recency_0_6_factor}
                          min={0.5} max={1} step={0.05} testid="rec-current"
                          onChange={(v) => patch("recency_0_6_factor", v)} />
                  <Slider label="7–12 months (relevant)" value={params.recency_7_12_factor}
                          min={0.3} max={1} step={0.05} testid="rec-relevant"
                          onChange={(v) => patch("recency_7_12_factor", v)} />
                  <Slider label="13–24 months (historical)" value={params.recency_13_24_factor}
                          min={0} max={0.8} step={0.05} testid="rec-historical"
                          onChange={(v) => patch("recency_13_24_factor", v)} />
                </div>
              </div>

              <div className="grid md:grid-cols-3 gap-6 mt-4">
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Recency months</div>
                  <NumInput label="Current window (months)" value={params.current_months}
                            onChange={(v) => patch("current_months", v)} testid="months-current" />
                  <NumInput label="Relevant window (months)" value={params.relevant_months}
                            onChange={(v) => patch("relevant_months", v)} testid="months-relevant" />
                  <NumInput label="Historical support window" value={params.historical_support_months}
                            onChange={(v) => patch("historical_support_months", v)} testid="months-historical" />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">CQS quality thresholds</div>
                  <NumInput label="Minimum usable" value={params.quality_min_usable}
                            onChange={(v) => patch("quality_min_usable", v)} testid="cqs-min-usable" />
                  <NumInput label="Reasonable match" value={params.quality_reasonable_min}
                            onChange={(v) => patch("quality_reasonable_min", v)} testid="cqs-reasonable" />
                  <NumInput label="Close match" value={params.quality_close_min}
                            onChange={(v) => patch("quality_close_min", v)} testid="cqs-close" />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Size similarity bands</div>
                  <div className="bg-muted/30 rounded p-3 text-xs space-y-2" data-testid="size-bands">
                    {(params.size_similarity_bands || []).map((b, i) => (
                      <div key={i} className="flex items-center justify-between gap-2">
                        <span>{b.label || `band ${i + 1}`}</span>
                        <input type="number" value={b.max_diff_pct} step={1}
                               onChange={(e) => {
                                 const next = [...params.size_similarity_bands];
                                 next[i] = { ...next[i], max_diff_pct: Number(e.target.value) };
                                 patch("size_similarity_bands", next);
                               }}
                               className="w-16 border border-border rounded px-2 py-1 text-right"
                               data-testid={`band-${i}-diff`} />
                        <span>%→</span>
                        <input type="number" value={b.factor} step={0.05}
                               onChange={(e) => {
                                 const next = [...params.size_similarity_bands];
                                 next[i] = { ...next[i], factor: Number(e.target.value) };
                                 patch("size_similarity_bands", next);
                               }}
                               className="w-16 border border-border rounded px-2 py-1 text-right"
                               data-testid={`band-${i}-factor`} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Section>
          )}

          {tab === "guidance" && (
            <Section title="GUIDE-1.0 — Price Guidance Rules" testid="config-guidance">
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Evidence count gates</div>
                  <NumInput label="Min direct for formal range" value={params.min_direct_for_formal_range}
                            onChange={(v) => patch("min_direct_for_formal_range", v)} testid="min-direct"
                            hint="Below this → no TREL Indicative Range emitted." />
                  <NumInput label="Limited-evidence max" value={params.limited_max_count}
                            onChange={(v) => patch("limited_max_count", v)} testid="limited-max" />
                  <NumInput label="Moderate-evidence max" value={params.moderate_max_count}
                            onChange={(v) => patch("moderate_max_count", v)} testid="moderate-max" />
                  <NumInput label="Strong-evidence min" value={params.strong_min_count}
                            onChange={(v) => patch("strong_min_count", v)} testid="strong-min" />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Outlier + percentile</div>
                  <NumInput label="IQR outlier multiplier" value={params.iqr_outlier_multiplier}
                            step={0.1} onChange={(v) => patch("iqr_outlier_multiplier", v)}
                            testid="iqr-mult"
                            hint="Only applied when there are ≥ 6 comparables." />
                  <NumInput label="Indicative lower percentile" value={params.indicative_lower_percentile}
                            onChange={(v) => patch("indicative_lower_percentile", v)} testid="pct-lo" />
                  <NumInput label="Indicative upper percentile" value={params.indicative_upper_percentile}
                            onChange={(v) => patch("indicative_upper_percentile", v)} testid="pct-hi" />
                </div>
              </div>

              <WeightsTable title="Confidence component weights (should sum to 100)"
                            weights={params.confidence_weights} testid="confidence"
                            hint="How quantity / quality / recency / dispersion contribute to the 0-100 confidence score."
                            onChange={(w) => patch("confidence_weights", w)} />
            </Section>
          )}

          {tab === "cqs" && (
            <Section title="Comparable Quality Score — baseline by class" testid="config-cqs">
              <div className="grid md:grid-cols-3 gap-4">
                {["residential", "commercial_industrial", "vacant_land"].map((cls) => (
                  <div key={cls} className="bg-muted/30 rounded p-3" data-testid={`cqs-class-${cls}`}>
                    <div className="text-sm font-medium capitalize mb-2">{cls.replace("_", " / ")}</div>
                    {Object.entries(params.cqs_baseline?.[cls] || {}).map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between py-1.5 text-sm">
                        <span className="capitalize">{k.replace(/_/g, " ")}</span>
                        <input type="number" value={v} min={0} step={1}
                               onChange={(e) => patchNested(
                                 "cqs_baseline", cls,
                                 { ...params.cqs_baseline[cls], [k]: Number(e.target.value) },
                               )}
                               className="w-16 border border-border rounded px-2 py-1 text-right"
                               data-testid={`cqs-${cls}-${k}`} />
                      </div>
                    ))}
                    <div className="text-xs text-muted-foreground mt-2">
                      Total: {Object.values(params.cqs_baseline?.[cls] || {}).reduce((a, b) => Number(a) + Number(b), 0)}
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {tab === "retention" && (
            <Section title="Data Retention & Governance" testid="config-retention">
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs text-muted-foreground max-w-xl">
                  Defines how long each data class is kept before archival. Soft-delete keeps history queryable; hard-delete removes it entirely. Use "Preview Impact" to see how many rows would be archived under the current settings before flipping any switch.
                </div>
                <div className="flex items-center gap-2 whitespace-nowrap">
                  <button onClick={doRetentionPreview} disabled={retentionBusy}
                          className="px-3 py-1.5 rounded border border-border text-sm hover:bg-muted disabled:opacity-60"
                          data-testid="retention-preview-btn">
                    {retentionBusy ? "…" : "Preview Impact"}
                  </button>
                  <button onClick={runRetentionNow} disabled={retentionBusy}
                          className="px-3 py-1.5 rounded bg-[#2A5B46] text-white text-sm hover:bg-[#204838] disabled:opacity-60"
                          data-testid="retention-run-btn">
                    Run Now
                  </button>
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Retention windows (days)</div>
                  <NumInput label="Raw source data" value={params.retention?.raw_source_data_days}
                            onChange={(v) => patchNested("retention", "raw_source_data_days", v)} testid="ret-raw"
                            hint="Original scraped payloads (raw_fields on market_listings)." />
                  <NumInput label="Normalized data" value={params.retention?.normalized_data_days}
                            onChange={(v) => patchNested("retention", "normalized_data_days", v)} testid="ret-norm"
                            hint="Canonicalised market_listings + master_properties." />
                  <NumInput label="Review cases" value={params.retention?.review_case_days}
                            onChange={(v) => patchNested("retention", "review_case_days", v)} testid="ret-review"
                            hint="Resolved review cases beyond this window are archived." />
                  <NumInput label="Audit log" value={params.retention?.audit_log_days}
                            onChange={(v) => patchNested("retention", "audit_log_days", v)} testid="ret-audit"
                            hint="Immutable audit trail retention (regulatory minimum: 7 years)." />
                </div>
                <div>
                  <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Deletion policy</div>
                  <label className="flex items-center gap-2 py-2 text-sm" data-testid="toggle-soft-delete">
                    <input type="checkbox"
                           checked={!!params.retention?.soft_delete_only}
                           onChange={(e) => patchNested("retention", "soft_delete_only", e.target.checked)} />
                    Soft delete only (never hard-delete)
                  </label>
                  <div className="text-xs text-muted-foreground mt-2">
                    Retention runs automatically once per 24h via the scheduler. Manual preview + run buttons above.
                  </div>

                  <div className="mt-6 pt-4 border-t border-border" data-testid="health-led-thresholds">
                    <div className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Pipeline Health LED thresholds</div>
                    <div className="text-xs text-muted-foreground mb-2">
                      Governs the global aggregation-health badge in the top-nav. Green when every active source meets the min success rate and no source has hit the red-failure streak.
                    </div>
                    <NumInput label="Amber below success rate (%)"
                              value={params.health_led?.amber_min_success_pct}
                              onChange={(v) => patchNested("health_led", "amber_min_success_pct", v)}
                              testid="led-amber-min" step={1} min={1} max={100}
                              hint="Any active source with a lower success rate flips the LED amber." />
                    <NumInput label="Red on consecutive failures ≥"
                              value={params.health_led?.red_consecutive_failures}
                              onChange={(v) => patchNested("health_led", "red_consecutive_failures", v)}
                              testid="led-red-streak" step={1} min={1} max={20}
                              hint="Any source hitting this streak length flips the LED red." />
                  </div>
                </div>
              </div>

              {retentionPreview && (
                <div className="mt-5 border-t border-border pt-4" data-testid="retention-preview-result">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-sm font-medium">
                      {retentionPreview.ran ? "Retention run — result" : "Preview — would soft-delete now"}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Mode: {retentionPreview.soft_delete_only ? "Soft delete only" : "Hard delete enabled"}
                    </div>
                  </div>
                  {retentionPreview.skipped ? (
                    <div className="text-sm text-muted-foreground">Skipped — {retentionPreview.reason}.</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                            <th className="py-2 pr-3">Collection</th>
                            <th className="py-2 pr-3">Retention window</th>
                            <th className="py-2 pr-3">Action</th>
                            <th className="py-2 pr-3 text-right">
                              {retentionPreview.ran ? "Archived" : "Would archive"}
                            </th>
                            <th className="py-2 pr-3 text-right">Candidates</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(retentionPreview.summary || {}).map(([coll, info]) => (
                            <tr key={coll} className="border-b border-border/60"
                                data-testid={`retention-row-${coll}`}>
                              <td className="py-2 pr-3 font-mono text-xs">{coll}</td>
                              <td className="py-2 pr-3">
                                {info.window_days ? `${info.window_days} days` : <span className="text-muted-foreground">disabled</span>}
                              </td>
                              <td className="py-2 pr-3 uppercase text-xs tracking-widest">
                                {info.action || (info.hard_deleted != null ? "hard_delete" : "soft_delete")}
                              </td>
                              <td className="py-2 pr-3 text-right tabular-nums font-medium">
                                {retentionPreview.ran
                                  ? (info.soft_deleted ?? info.hard_deleted ?? 0)
                                  : (info.candidates ?? 0)}
                              </td>
                              <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground">
                                {info.candidates ?? "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground mt-3">
                    {retentionPreview.ran
                      ? `Executed at ${retentionPreview.ran_at?.slice(0, 19)?.replace("T", " ")}. Preview again to confirm results.`
                      : `Snapshot at ${retentionPreview.previewed_at?.slice(0, 19)?.replace("T", " ")}. Nothing has been changed yet.`}
                  </div>
                </div>
              )}
            </Section>
          )}

          {tab === "advanced" && (
            <Section title="Advanced — raw JSON" testid="config-advanced">
              <div className="text-xs text-muted-foreground mb-2">
                Read-only view of the currently-edited parameters. Publish above to save.
              </div>
              <pre className="bg-muted/40 rounded p-3 text-xs overflow-x-auto max-h-[600px]"
                   data-testid="config-json-preview">
{JSON.stringify(params, null, 2)}
              </pre>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}
