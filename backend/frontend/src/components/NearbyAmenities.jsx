import React, { useState } from "react";
import { Sparkles, GraduationCap, HeartPulse, ShoppingBag, Waves, Bus, TreePine, ChevronDown, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

const CATEGORY_ICON = {
  schools: GraduationCap,
  hospitals: HeartPulse,
  shopping: ShoppingBag,
  beaches: Waves,
  transport: Bus,
  recreation: TreePine,
};

/**
 * Buyer-facing collapsible panel that fetches an AI-generated summary of
 * nearby amenities (schools, hospitals, shopping, beaches, transport,
 * recreation) for a given property location.
 *
 * Data comes from POST /api/ai/nearby-amenities and is powered by Claude
 * Sonnet 4.5 via the Emergent LLM key.
 */
export default function NearbyAmenities({ suburb = "", city = "", province = "", property_type = "", testId = "nearby-amenities" }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);

  const canRun = Boolean(suburb || city);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !data && !loading && canRun) {
      setLoading(true);
      setError("");
      try {
        const res = await api.post("/ai/nearby-amenities", { suburb, city, province, property_type });
        setData(res.data);
      } catch (e) {
        if (e?.response?.status === 503) setUnavailable(true);
        else setError("Couldn't load nearby amenities. Please try again shortly.");
      } finally {
        setLoading(false);
      }
    }
  };

  if (!canRun || unavailable) return null;

  return (
    <div className="mt-6 rounded-2xl border border-border bg-white overflow-hidden" data-testid={testId}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-sand-50"
        data-testid={`${testId}-toggle`}
      >
        <span className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-[#0d50e0]/10 text-[#0d50e0]">
            <Sparkles className="w-4 h-4" />
          </span>
          <span className="font-serif text-xl text-ink-900">Nearby amenities</span>
          <span className="text-xs text-muted-foreground hidden sm:inline">AI summary</span>
        </span>
        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-border" data-testid={`${testId}-body`}>
          {loading && (
            <div className="py-8 flex items-center justify-center gap-2 text-sm text-muted-foreground" data-testid={`${testId}-loading`}>
              <Loader2 className="w-4 h-4 animate-spin" /> Finding nearby amenities…
            </div>
          )}
          {!loading && error && (
            <div className="py-6 text-sm text-destructive" data-testid={`${testId}-error`}>{error}</div>
          )}
          {!loading && !error && data && (
            <div className="pt-4">
              {data.location_label && (
                <div className="text-xs text-muted-foreground mb-4" data-testid={`${testId}-location`}>
                  Around <span className="font-medium text-ink-900">{data.location_label}</span>
                </div>
              )}
              {data.categories?.length === 0 && (
                <div className="text-sm text-muted-foreground" data-testid={`${testId}-empty`}>
                  No nearby amenities information available for this area.
                </div>
              )}
              <div className="grid sm:grid-cols-2 gap-4">
                {data.categories?.map((cat) => {
                  const Icon = CATEGORY_ICON[cat.key] || Sparkles;
                  return (
                    <div key={cat.key} className="rounded-xl border border-border p-4" data-testid={`${testId}-cat-${cat.key}`}>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-[#0d50e0]/10 text-[#0d50e0]">
                          <Icon className="w-4 h-4" />
                        </span>
                        <h4 className="font-medium text-ink-900">{cat.label}</h4>
                      </div>
                      <ul className="space-y-2">
                        {cat.items?.map((it, i) => (
                          <li key={`${cat.key}-${i}`} className="text-sm">
                            <div className="flex items-baseline justify-between gap-2">
                              <span className="font-medium text-ink-900">{it.name}</span>
                              {it.distance_hint && (
                                <span className="text-[11px] text-muted-foreground whitespace-nowrap">{it.distance_hint}</span>
                              )}
                            </div>
                            {it.note && <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{it.note}</p>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
              {data.disclaimer && (
                <p className="mt-4 text-[11px] text-muted-foreground italic" data-testid={`${testId}-disclaimer`}>
                  {data.disclaimer}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
