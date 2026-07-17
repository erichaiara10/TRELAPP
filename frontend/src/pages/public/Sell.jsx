import React, { useState } from "react";
import { usePage } from "@/lib/usePage";
import LeadFormPage, { RequiredMark } from "./LeadFormPage";
import PhotoUploader from "@/components/PhotoUploader";
import MapCoordsField from "@/components/MapCoordsField";

export default function Sell() {
  const { sections } = usePage("sell");
  const hero = sections.hero || {};
  const benefits = sections.benefits || [];
  const [prop, setProp] = useState({ property_type: "house", price: "", location: "", suburb: "", bedrooms: "", map_coords: "" });
  const [photos, setPhotos] = useState([]);

  const extra = (
    <>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Property type<RequiredMark /></span>
        <select value={prop.property_type} onChange={(e) => setProp({ ...prop, property_type: e.target.value })} data-testid="sell_form-type" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="house">House</option><option value="apartment">Apartment</option>
          <option value="townhouse">Townhouse</option><option value="land">Land</option><option value="commercial">Commercial</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Expected price (PGK)<RequiredMark /></span>
        <input type="number" placeholder="e.g. 850000" value={prop.price} onChange={(e) => setProp({ ...prop, price: e.target.value })} data-testid="sell_form-price" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Location / City<RequiredMark /></span>
        <input placeholder="e.g. Port Moresby" value={prop.location} onChange={(e) => setProp({ ...prop, location: e.target.value })} data-testid="sell_form-location" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Suburb</span>
        <input placeholder="e.g. Boroko" value={prop.suburb} onChange={(e) => setProp({ ...prop, suburb: e.target.value })} data-testid="sell_form-suburb" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <MapCoordsField
        label="Google Maps location (optional)"
        value={prop.map_coords}
        onChange={(v) => setProp({ ...prop, map_coords: v })}
        testId="sell_form-map-coords"
      />
      <PhotoUploader value={photos} onChange={setPhotos} testId="sell_form-photos" />
    </>
  );

  const extraRequired = () =>
    Boolean(prop.property_type && String(prop.price).trim() && prop.location.trim());

  return (
    <div>
      <LeadFormPage
        source="sell_form"
        kicker={hero.kicker || "SELL WITH TREL"}
        title={hero.heading || "List your property"}
        intro={hero.intro || ""}
        heroImage={hero.image}
        extra={extra}
        extraPayload={() => ({ ...prop, photos })}
        extraRequired={extraRequired}
      />
      {benefits.length > 0 && (
        <section className="container-tight pb-16 max-w-4xl" data-testid="sell-benefits">
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Why list with TREL</div>
          <h2 className="font-serif text-3xl mt-2">What you get</h2>
          <div className="mt-6 grid md:grid-cols-3 gap-4">
            {benefits.map((b, i) => (
              <div key={i} className="bg-white rounded-2xl p-5 border border-border" data-testid={`sell-benefit-${i}`}>
                <div className="font-serif text-xl">{b.title}</div>
                <p className="text-sm text-ink-700 mt-2 whitespace-pre-line">{b.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
