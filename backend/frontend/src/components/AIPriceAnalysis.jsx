import React, { useEffect, useState } from "react";
import { Sparkles, ChevronDown, ChevronUp, TrendingUp, TrendingDown, CheckCircle2, Loader2, AlertCircle, X } from "lucide-react";
import { api, formatError } from "@/lib/api";

const BRAND_BLUE = "#0d50e0";

const fmtK = (n) => {
  if (n == null || isNaN(n)) return "K —";
  return `K ${Math.round(Number(n)).toLocaleString()}`;
};

const VERDICT_META = {
  insufficient: { label: "Insufficient evidence", tone: "bg-slate-50 text-slate-700 border-slate-200", Icon: AlertCircle },
  fair: { label: "Fair price", tone: "bg-emerald-50 text-emerald-700 border-emerald-200", Icon: CheckCircle2 },
  overpriced: { label: "Overpriced", tone: "bg-terracotta-50 text-terracotta-600 border-terracotta-200", Icon: TrendingUp },
  underpriced: { label: "Underpriced", tone: "bg-amber-50 text-amber-700 border-amber-200", Icon: TrendingDown },
};

// Audience-aware, cautious language for the recommendation sentence.
// The AI's raw text is intentionally REPLACED with these safe strings so the
// tone stays consistent regardless of what Claude returns.
const RECOMMENDATION_COPY = {
  buyer: {
    insufficient: "There are not yet enough unique comparable properties for a formal TREL price range.",
    underpriced: "Based on similar listings, this appears to be a competitive offer.",
    overpriced:  "This price suggests it may be above the current area average.",
    fair:        "This price appears aligned with similar listings in the area.",
  },
  seller: {
    insufficient: "There are not yet enough unique comparable properties for a formal TREL price range.",
    underpriced: "Your pricing appears competitive for the current market.",
    overpriced:  "Available data suggests this price may be higher than average for this location.",
    fair:        "Your pricing appears aligned with the current market for this area.",
  },
  admin: {
    insufficient: "Fewer than three unique comparables are available; no formal range has been produced.",
    underpriced: "Current analysis suggests room for value capture — review market data.",
    overpriced:  "Pricing appears high compared to similar records — consider a strategy review.",
    fair:        "Pricing appears aligned with comparable records in the market.",
  },
};

const DISCLAIMER = "This analysis is based on available data and should be used as a guide only.";

function pickRecommendation(audience, verdict) {
  const bucket = RECOMMENDATION_COPY[audience] || RECOMMENDATION_COPY.buyer;
  return bucket[verdict] || bucket.fair;
}

/** Panel body — used inline (Sell/PropertyDetail) or inside a modal (PropertyCard). */
function AnalysisBody({ data, loading, error, onClose, testIdPrefix, buyerFacing, audience }) {
  if (loading) {
    return (
      <div className="p-5 flex items-center gap-3 text-sm text-muted-foreground" data-testid={`${testIdPrefix}-loading`}>
        <Loader2 className="w-4 h-4 animate-spin" style={{ color: BRAND_BLUE }} />
        Analysing comparable listings…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-5 flex items-start gap-2 text-sm text-destructive" data-testid={`${testIdPrefix}-error`}>
        <AlertCircle className="w-4 h-4 mt-0.5" /> {error}
      </div>
    );
  }
  if (!data) return null;
  const v = VERDICT_META[data.verdict] || VERDICT_META.fair;
  // Softened verdict wording per audience so the label doesn't read harshly.
  // Buyer & seller both see neutral language; admin keeps the raw analyst label.
  const softVerdict = (() => {
    if (data.verdict === "insufficient") return "Insufficient evidence";
    if (audience === "seller") {
      return data.verdict === "overpriced" ? "Above market range"
           : data.verdict === "underpriced" ? "Below market range"
           : "Aligned with market";
    }
    if (buyerFacing || audience === "buyer") {
      return data.verdict === "overpriced" ? "Above market"
           : data.verdict === "underpriced" ? "Below market"
           : "In line with market";
    }
    return v.label; // admin — keep raw label
  })();
  // Audience-aware, cautious recommendation copy (overrides whatever the LLM returned)
  const recommendation = pickRecommendation(audience, data.verdict);

  return (
    <div className="relative p-5 space-y-4" data-testid={`${testIdPrefix}-body`}>
      {onClose && (
        <button onClick={onClose} className="absolute top-3 right-3 p-1 rounded hover:bg-sand-100" aria-label="Close" data-testid={`${testIdPrefix}-close`}>
          <X className="w-4 h-4" />
        </button>
      )}
      {/* Verdict banner */}
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${v.tone}`} data-testid={`${testIdPrefix}-verdict`}>
        <v.Icon className="w-3.5 h-3.5" /> {softVerdict}
      </div>

      {/* Range + average */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="rounded-lg bg-sand-50 border border-border p-3">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Indicative price range</div>
          <div className="text-sm font-semibold text-ink-900 mt-1" data-testid={`${testIdPrefix}-range`}>
            {data.formal_range_available === false ? "Not available" : `${fmtK(data.range_min)} – ${fmtK(data.range_max)}`}
          </div>
        </div>
        <div className="rounded-lg bg-sand-50 border border-border p-3">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Median comparable</div>
          <div className="text-sm font-semibold text-ink-900 mt-1" data-testid={`${testIdPrefix}-average`}>{fmtK(data.median ?? data.average)}</div>
        </div>
        <div className="rounded-lg bg-sand-50 border border-border p-3 col-span-2 sm:col-span-1">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Comparables</div>
          <div className="text-sm font-semibold text-ink-900 mt-1">{data.sample_size ?? data.comparables?.length ?? 0} unique</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-lg border p-2"><span className="block text-muted-foreground">TREL Internal</span><b>{data.internal_count ?? 0}</b></div>
        <div className="rounded-lg border p-2"><span className="block text-muted-foreground">External Market</span><b>{data.external_count ?? 0}</b></div>
        <div className="rounded-lg border p-2"><span className="block text-muted-foreground">Evidence</span><b className="capitalize">{String(data.evidence_strength || "unknown").toLowerCase()}</b></div>
      </div>

      {/* Audience-aware Recommendation */}
      <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: `${BRAND_BLUE}10`, color: BRAND_BLUE }} data-testid={`${testIdPrefix}-recommendation`}>
        <span className="font-medium">Recommendation: </span>{recommendation}
      </div>

      {/* Comparables */}
      {data.comparables?.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Similar properties</div>
          <ul className="space-y-1" data-testid={`${testIdPrefix}-comparables`}>
            {data.comparables.map((c, i) => (
              <li key={i} className="flex items-center justify-between gap-2 px-3 py-2 rounded-md bg-white border border-border text-sm">
                <div className="min-w-0 flex-1 truncate">
                  <span className="text-ink-900">{c.title || `${c.property_type} in ${c.suburb}`}</span>
                  <span className="text-xs text-muted-foreground ml-2">· {c.suburb}</span>
                </div>
                <span className="font-medium text-ink-900 shrink-0">{fmtK(c.price)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Universal cautious-tone disclaimer */}
      <p className="text-[11px] italic text-muted-foreground leading-relaxed" data-testid={`${testIdPrefix}-disclaimer`}>
        {DISCLAIMER}
      </p>
    </div>
  );
}

/**
 * Reusable AI Price Analysis component.
 *
 * Props:
 *  - property_type, listing_type ('sale'|'rent'), price, province, city, suburb, bedrooms
 *  - variant: 'inline' (default — expandable panel) or 'compact' (icon button that opens a modal)
 *  - buyerFacing: true when embedded on Buy/Rent (softens verdict wording)
 *
 * The button is only shown when both `property_type` AND (city or suburb) are set.
 */
export default function AIPriceAnalysis({
  property_id, property_type, listing_type = "sale", price, province, city, suburb, local_area, bedrooms,
  bathrooms, parking, land_area_sqm, building_area_sqm, property_condition, tenure_type,
  street_name, nearby_landmark,
  variant = "inline",
  buyerFacing = false,
  audience = "buyer",
  testIdPrefix = "ai-price",
  autoRun = false,
}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const canRun = Boolean(property_type && (city || suburb) && Number(price) > 0);

  const run = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (data) return; // already fetched — just re-expand
    setLoading(true);
    setError("");
    try {
      const { data: resp } = await api.post("/ai/price-analysis", {
        property_id: property_id || null, property_type, listing_type, price: Number(price) || 0,
        province: province || null, city: city || null, suburb: suburb || null, local_area: local_area || null,
        bedrooms: Number(bedrooms) || null,
        bathrooms: bathrooms == null ? null : Number(bathrooms),
        parking: parking == null ? null : Number(parking),
        land_area_sqm: Number(land_area_sqm) || null,
        building_area_sqm: Number(building_area_sqm) || null,
        property_condition: property_condition || null, tenure_type: tenure_type || null,
        street_name: street_name || null, nearby_landmark: nearby_landmark || null,
      });
      setData(resp);
    } catch (e) {
      setError(formatError(e));
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (autoRun && canRun && !open && !data && !loading) run();
    // Auto-run is intentionally evaluated only when the deep-linked comparison becomes available.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun, canRun]);

  if (!canRun) return null;

  const btnLabel = "Compare Price";
  const testId = `${testIdPrefix}-btn`;

  if (variant === "compact") {
    return (
      <>
        <button
          type="button"
          onClick={run}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-white text-[11px] font-medium shadow-sm hover:shadow-md transition-all"
          style={{ backgroundColor: BRAND_BLUE }}
          title={btnLabel}
          data-testid={testId}
        >
          <Sparkles className="w-3 h-3" /> AI
        </button>
        {open && (
          <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setOpen(false)}>
            <div
              className="relative bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl"
              onClick={(e) => e.stopPropagation()}
              data-testid={`${testIdPrefix}-modal`}
            >
              <div className="px-5 pt-5 pb-2 flex items-center gap-2">
                <Sparkles className="w-4 h-4" style={{ color: BRAND_BLUE }} />
                <div className="font-medium text-ink-900">{btnLabel}</div>
              </div>
              <AnalysisBody data={data} loading={loading} error={error} onClose={() => setOpen(false)} testIdPrefix={testIdPrefix} buyerFacing={buyerFacing} audience={audience} />
            </div>
          </div>
        )}
      </>
    );
  }

  // Inline (default) — button expands a panel below
  return (
    <div className="w-full" data-testid={`${testIdPrefix}-container`}>
      <button
        type="button"
        onClick={run}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium shadow-sm hover:shadow-md transition-all"
        style={{ backgroundColor: BRAND_BLUE }}
        data-testid={testId}
      >
        <Sparkles className="w-4 h-4" /> {btnLabel}
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {open && (
        <div
          className="mt-3 rounded-xl border relative bg-white shadow-sm"
          style={{ borderColor: `${BRAND_BLUE}30` }}
          data-testid={`${testIdPrefix}-panel`}
        >
          <AnalysisBody data={data} loading={loading} error={error} testIdPrefix={testIdPrefix} buyerFacing={buyerFacing} audience={audience} />
        </div>
      )}
    </div>
  );
}
