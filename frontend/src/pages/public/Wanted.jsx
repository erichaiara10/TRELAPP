import React, { useEffect, useState } from "react";
import { usePage } from "@/lib/usePage";
import LeadFormPage from "./LeadFormPage";
import { api } from "@/lib/api";

export default function Wanted() {
  const { sections } = usePage("wanted");
  const hero = sections.hero || {};
  const [req, setReq] = useState({ intent: "buy", property_type: "house", min_price: "", max_price: "", min_bedrooms: "", locations: "" });
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/requirements/public").then((r) => setItems(r.data)).catch(() => {}); }, []);

  const extra = (
    <>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">I want to</span>
        <select value={req.intent} onChange={(e) => setReq({ ...req, intent: e.target.value })} data-testid="wanted_form-intent" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="buy">Buy</option><option value="rent">Rent</option><option value="either">Either</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Property type</span>
        <select value={req.property_type} onChange={(e) => setReq({ ...req, property_type: e.target.value })} data-testid="wanted_form-type" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="house">House</option><option value="apartment">Apartment</option><option value="townhouse">Townhouse</option>
          <option value="land">Land</option><option value="commercial">Commercial</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Min price (PGK)</span>
        <input type="number" placeholder="e.g. 400000" value={req.min_price} onChange={(e) => setReq({ ...req, min_price: e.target.value })} data-testid="wanted_form-min" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Max price (PGK)</span>
        <input type="number" placeholder="e.g. 900000" value={req.max_price} onChange={(e) => setReq({ ...req, max_price: e.target.value })} data-testid="wanted_form-max" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Bedrooms (min)</span>
        <input type="number" placeholder="e.g. 3" value={req.min_bedrooms} onChange={(e) => setReq({ ...req, min_bedrooms: e.target.value })} data-testid="wanted_form-beds" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Preferred locations</span>
        <input placeholder="Comma-separated (e.g. Waigani, Boroko)" value={req.locations} onChange={(e) => setReq({ ...req, locations: e.target.value })} data-testid="wanted_form-locations" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
    </>
  );

  const payload = () => ({
    intent: req.intent, property_type: req.property_type,
    min_price: Number(req.min_price) || 0, max_price: Number(req.max_price) || 0,
    min_bedrooms: Number(req.min_bedrooms) || 0,
    locations: req.locations.split(",").map((s) => s.trim()).filter(Boolean),
  });

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
