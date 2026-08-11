// Public Price Compare — 4 customer-facing workflows sharing one page,
// selected by :workflow (seller / buyer / landlord / renter) or a landing
// page when no workflow is chosen.
//
// Powered by POST /api/public/guidance/run (no auth). Backend applies the
// GUIDE-1.0 algorithm and returns the TREL Indicative Range, weighted
// median, confidence label, and position (BELOW / WITHIN / ABOVE).
import React, { useState } from "react";
import axios from "axios";
import { Link, useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WORKFLOWS = {
  seller:   { title: "Seller Guidance",       purpose: "sale", askingLabel: "Your target listing price (PGK)", ctaLabel: "Get selling guidance", intro: "Discover how your home stacks up against active listings on the same street, local area and suburb. Every figure is backed by named comparables you can drill into." },
  buyer:    { title: "Buyer Price Check",     purpose: "sale", askingLabel: "Asking price you're considering (PGK)", ctaLabel: "Check this price",     intro: "Paste the asking price and see whether it sits below, within or above the evidence-based range for the area." },
  landlord: { title: "Landlord Rent Guidance", purpose: "rent", askingLabel: "Your target monthly rent (PGK)",    ctaLabel: "Get rent guidance",    intro: "See what similar properties are currently asking per month across the same suburb, street and local area." },
  renter:   { title: "Renter Rent Check",     purpose: "rent", askingLabel: "Monthly rent you're considering (PGK)", ctaLabel: "Check this rent",     intro: "Find out how the advertised rent compares against the evidence-based monthly range for the area." },
};

function money(v, ccy = "PGK") {
  if (v == null) return "—";
  return new Intl.NumberFormat("en-PG", { style: "currency", currency: ccy, maximumFractionDigits: 0 }).format(v);
}

export default function PriceCompare() {
  const { workflow } = useParams();
  const nav = useNavigate();
  const meta = WORKFLOWS[workflow];

  if (!meta) return <Landing nav={nav} />;

  return <Workflow workflow={workflow} meta={meta} />;
}

function Landing({ nav }) {
  return (
    <div className="max-w-6xl mx-auto py-12 px-6" data-testid="price-compare-landing">
      <div className="text-[11px] uppercase tracking-[0.22em] text-[#2A5B46]">TREL Price Compare</div>
      <h1 className="text-4xl sm:text-5xl font-serif mt-2">Evidence-based property guidance for PNG</h1>
      <p className="text-muted-foreground mt-3 max-w-2xl">Every guidance run pulls comparable listings across the same street, local area and suburb — then applies TREL's rule-based algorithm to produce an Indicative Range and confidence label. Nothing invented, everything auditable.</p>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mt-10">
        {Object.entries(WORKFLOWS).map(([key, w]) => (
          <button key={key} onClick={() => nav(`/price-compare/${key}`)}
                  className="text-left bg-white border border-border hover:border-[#2A5B46] rounded-lg p-5 transition-colors"
                  data-testid={`pc-tile-${key}`}>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              {w.purpose === "sale" ? "For Sale" : "For Rent"}
            </div>
            <div className="text-lg font-semibold mt-1">{w.title}</div>
            <p className="text-xs text-muted-foreground mt-2">{w.intro}</p>
            <div className="text-sm text-[#2A5B46] mt-4">Start →</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function Workflow({ workflow, meta }) {
  const [form, setForm] = useState({
    purpose: meta.purpose,
    property_class: "residential",
    property_subtype: "House",
    suburb: "",
    street: "",
    local_area: "",
    bedrooms: 3, bathrooms: 2,
    land_area_m2: 600, building_area_m2: 180,
    subject_asking_price: "",
  });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.suburb) { toast.error("Suburb is required"); return; }
    setBusy(true); setResult(null);
    try {
      const payload = { ...form, workflow };
      const { data } = await axios.post(`${API}/public/guidance/run`, payload);
      setResult(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Unable to generate guidance");
    } finally { setBusy(false); }
  };

  return (
    <div className="max-w-5xl mx-auto py-10 px-6" data-testid={`pc-workflow-${workflow}`}>
      <Link to="/price-compare" className="text-xs text-muted-foreground underline">← All price-compare tools</Link>
      <div className="text-[11px] uppercase tracking-[0.22em] text-[#2A5B46] mt-3">TREL Price Compare</div>
      <h1 className="text-3xl sm:text-4xl font-serif mt-2">{meta.title}</h1>
      <p className="text-muted-foreground mt-2 max-w-2xl">{meta.intro}</p>

      <div className="grid lg:grid-cols-2 gap-6 mt-8">
        <div className="bg-white border border-border rounded-lg p-5" data-testid="pc-subject-form">
          <div className="text-sm font-medium mb-3">Subject Property</div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <SelectField label="Property class" value={form.property_class} testid="pc-class"
                         options={["residential", "commercial_industrial", "vacant_land"]}
                         onChange={(v) => setForm({ ...form, property_class: v })} />
            <TextField label="Subtype" value={form.property_subtype} testid="pc-subtype"
                       onChange={(v) => setForm({ ...form, property_subtype: v })} />
            <TextField label="Suburb *" value={form.suburb} testid="pc-suburb"
                       onChange={(v) => setForm({ ...form, suburb: v })} />
            <TextField label="Street" value={form.street} testid="pc-street"
                       onChange={(v) => setForm({ ...form, street: v })} />
            <TextField label="Local area" value={form.local_area} testid="pc-local-area"
                       onChange={(v) => setForm({ ...form, local_area: v })} />
            <NumField label="Bedrooms" value={form.bedrooms} testid="pc-beds"
                      onChange={(v) => setForm({ ...form, bedrooms: v })} />
            <NumField label="Bathrooms" value={form.bathrooms} testid="pc-baths"
                      onChange={(v) => setForm({ ...form, bathrooms: v })} />
            <NumField label="Land (m²)" value={form.land_area_m2} testid="pc-land"
                      onChange={(v) => setForm({ ...form, land_area_m2: v })} />
            <NumField label="Building (m²)" value={form.building_area_m2} testid="pc-building"
                      onChange={(v) => setForm({ ...form, building_area_m2: v })} />
            <NumField label={meta.askingLabel} value={form.subject_asking_price} testid="pc-asking"
                      onChange={(v) => setForm({ ...form, subject_asking_price: v })} />
          </div>
          <button onClick={submit} disabled={busy}
                  className="w-full mt-5 px-4 py-2.5 bg-[#2A5B46] text-white rounded text-sm hover:bg-[#204838] disabled:opacity-60"
                  data-testid="pc-submit">
            {busy ? "Analysing comparables…" : meta.ctaLabel}
          </button>
        </div>

        <div>
          {result ? <Result workflow={workflow} result={result} /> : (
            <div className="bg-white border border-dashed border-border rounded-lg p-6 text-sm text-muted-foreground"
                 data-testid="pc-empty">
              Fill out the form and click "{meta.ctaLabel}" — you'll get an evidence-based range, a confidence label, and (if you provided a price) a position marker.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Result({ workflow, result }) {
  const isRent = result.purpose === "rent";
  const ccy = "PGK";
  const label = (l) => ({ strong: "Strong", moderate: "Moderate", limited: "Limited", insufficient: "Insufficient" }[l] || l);
  const confColor = ({ strong: "#10B981", moderate: "#4B8B70", limited: "#F59E0B", insufficient: "#DC2626" }[result.confidence_label]) || "#6B7280";
  const positionColor = ({ BELOW: "#10B981", WITHIN: "#4B8B70", ABOVE: "#DC2626" }[result.position]) || "#6B7280";

  return (
    <div className="space-y-4" data-testid="pc-result">
      <div className="bg-white border border-border rounded-lg p-5">
        <div className="text-xs uppercase tracking-widest text-muted-foreground">TREL Indicative {isRent ? "monthly rent" : "price"} range</div>
        <div className="text-3xl font-serif mt-1 tabular-nums" data-testid="pc-range">
          {result.trel_indicative_range?.p25
            ? `${money(result.trel_indicative_range.p25, ccy)} – ${money(result.trel_indicative_range.p75, ccy)}`
            : "Insufficient evidence"}
        </div>
        <div className="mt-2 text-sm text-muted-foreground">
          Weighted median <strong className="tabular-nums" data-testid="pc-weighted-median">{money(result.weighted_median, ccy)}</strong>
          {" · "}Observed {money(result.observed_range?.min, ccy)}–{money(result.observed_range?.max, ccy)}
        </div>
        <div className="flex items-center gap-4 mt-4">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Confidence</div>
          <span className="text-xs uppercase tracking-widest text-white px-2 py-0.5 rounded"
                style={{ background: confColor }} data-testid="pc-confidence">
            {label(result.confidence_label)}
          </span>
          <span className="text-xs text-muted-foreground">{result.confidence_score?.toFixed?.(0)}/100 · {result.comparable_count} comparables</span>
        </div>
      </div>

      {result.position && (
        <div className="bg-white border border-border rounded-lg p-5" data-testid="pc-position">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Your price is</div>
          <div className="text-3xl font-serif mt-1" style={{ color: positionColor }}>
            {result.position}
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            {result.delta_pct == null ? "" :
              `${result.delta_pct > 0 ? "+" : ""}${result.delta_pct.toFixed(1)}% vs weighted median.`}
          </div>
          <div className="text-xs text-muted-foreground mt-2">
            {result.position === "BELOW"  && (workflow === "seller" || workflow === "landlord"
                ? "You may be leaving money on the table. Consider a higher list price with justification."
                : "This looks like a strong-value opportunity relative to comparable evidence.")}
            {result.position === "WITHIN" && "Your price is aligned with the evidence-based range."}
            {result.position === "ABOVE"  && (workflow === "seller" || workflow === "landlord"
                ? "Priced above the range — expect longer time on market unless justified by outstanding features."
                : "Priced above the range — negotiate or ask what justifies the premium.")}
          </div>
        </div>
      )}

      {(result.comparables_sample || []).length > 0 && (
        <div className="bg-white border border-border rounded-lg p-5" data-testid="pc-comparables">
          <div className="text-sm font-medium mb-2">Top comparables included</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-1 pr-2">Tier</th>
                <th className="py-1 pr-2">CQS</th>
                <th className="py-1 pr-2">Recency</th>
                <th className="py-1 pr-2 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {result.comparables_sample.map((c, i) => (
                <tr key={i} className="border-t border-border/60">
                  <td className="py-1 pr-2">{c.tier?.replace(/_/g, " ")}</td>
                  <td className="py-1 pr-2 tabular-nums">{c.quality_score?.toFixed?.(0)}</td>
                  <td className="py-1 pr-2 tabular-nums">{c.recency_factor?.toFixed?.(2)}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{money(c.value, ccy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[10px] text-muted-foreground mt-3">
            Algorithm {result.algorithm_version} · configuration {result.config_version}. All figures are indicative and subject to data coverage.
          </div>
        </div>
      )}
    </div>
  );
}

function TextField({ label, value, onChange, testid }) {
  return (
    <label className="block" data-testid={`field-${testid}`}>
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <input value={value ?? ""} onChange={(e) => onChange(e.target.value)}
             className="w-full border border-border rounded px-2 py-1.5 text-sm"
             data-testid={`input-${testid}`} />
    </label>
  );
}
function NumField({ label, value, onChange, testid }) {
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
function SelectField({ label, value, options, onChange, testid }) {
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
