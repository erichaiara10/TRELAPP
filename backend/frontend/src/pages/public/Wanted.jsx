import React, { useEffect, useState } from "react";
import { usePage } from "@/lib/usePage";
import LeadFormPage from "./LeadFormPage";
import LocationPicker from "@/components/LocationPicker";
import PriceInput from "@/components/PriceInput";
import PropertyTypeSelect from "@/components/PropertyTypeSelect";
import { api } from "@/lib/api";
import { isPlaceholder } from "@/lib/validators";

function RequiredMark() { return <span className="text-destructive ml-0.5" aria-label="required">*</span>; }

export default function Wanted() {
  const { sections } = usePage("wanted");
  const hero = sections.hero || {};
  const [req, setReq] = useState({ intent: "buy", property_type: "", min_price: "", max_price: "", min_bedrooms: "", province: "", city: "", suburb: "" });
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/requirements/public").then((r) => setItems(r.data)).catch(() => {}); }, []);

  const priceErr = (() => {
    const min = Number(req.min_price) || 0;
    const max = Number(req.max_price) || 0;
    if (min > 0 && max > 0 && max < min) return "Max price must be greater than or equal to min price";
    return "";
  })();

  const extra = (
    <>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">I want to<RequiredMark /></span>
        <select value={req.intent} onChange={(e) => setReq({ ...req, intent: e.target.value })} data-testid="wanted_form-intent" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="buy">Buy</option><option value="rent">Rent</option><option value="either">Either</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Property type</span>
        <div className="mt-1">
          <PropertyTypeSelect value={req.property_type} onChange={(v) => setReq({ ...req, property_type: v })} testId="wanted_form-type" />
        </div>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Min price (PGK)<RequiredMark /></span>
        <div className="mt-1"><PriceInput value={req.min_price} onChange={(v) => setReq({ ...req, min_price: v })} testId="wanted_form-min" /></div>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Max price (PGK)</span>
        <div className="mt-1"><PriceInput value={req.max_price} onChange={(v) => setReq({ ...req, max_price: v })} testId="wanted_form-max" error={priceErr} /></div>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Bedrooms (min)</span>
        <input type="number" min="0" placeholder="e.g. 3" value={req.min_bedrooms} onChange={(e) => setReq({ ...req, min_bedrooms: e.target.value.replace(/\D/g, "") })} data-testid="wanted_form-beds" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <LocationPicker
        value={{ province: req.province, city: req.city, suburb: req.suburb }}
        onChange={(v) => setReq({ ...req, province: v.province, city: v.city, suburb: v.suburb })}
        testIdPrefix="wanted_form-location"
        required
      />
    </>
  );

  const payload = () => ({
    intent: req.intent, property_type: req.property_type,
    min_price: Number(req.min_price) || 0, max_price: Number(req.max_price) || 0,
    min_bedrooms: Number(req.min_bedrooms) || 0,
    province: req.province, city: req.city, suburb: req.suburb,
    locations: [req.city, req.suburb].filter(Boolean),
  });

  // Validate Wanted-specific rules: intent, min_price>0, province, city, plus min≤max.
  const extraValidator = () => {
    const errs = {};
    if (!req.intent) errs.intent = "Please select what you'd like to do";
    if (!(Number(req.min_price) > 0)) errs.min_price = "Please enter a minimum price";
    if (isPlaceholder(req.province)) errs.province = "Please select a province";
    if (isPlaceholder(req.city)) errs.city = "Please select a city";
    if (priceErr) errs.max_price = priceErr;
    return errs;
  };
  const extraRequired = () => Object.keys(extraValidator()).length === 0;

  return (
    <>
      <LeadFormPage
        source="wanted_form"
        kicker={hero.kicker || "PROPERTY WANTED"}
        title={hero.heading || "Tell us what you're looking for"}
        intro={hero.intro || ""}
        heroImage={hero.image}
        extra={extra}
        extraPayload={payload}
        extraRequired={extraRequired}
        extraValidator={extraValidator}
      />
      <div className="container-tight pb-16 max-w-4xl">
        <h2 className="font-serif text-2xl mb-4">Current active requirements</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((w, i) => (
            <div key={i} className="bg-white rounded-2xl p-5 border border-border">
              <div className="flex gap-2 text-xs">
                <span className="px-2 py-0.5 rounded-full bg-terracotta-50 text-terracotta-600 capitalize">{w.intent}</span>
                <span className="px-2 py-0.5 rounded-full bg-sand-100 capitalize">{w.property_type || "any"}</span>
              </div>
              <div className="font-serif text-lg mt-2">Budget up to {(w.max_price || 0).toLocaleString()} PGK</div>
              <div className="text-sm text-muted-foreground mt-1">{w.notes}</div>
            </div>
          ))}
          {items.length === 0 && <div className="text-sm text-muted-foreground">No active requirements listed yet.</div>}
        </div>
      </div>
    </>
  );
}
