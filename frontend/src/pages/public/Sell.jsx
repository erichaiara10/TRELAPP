import React, { useState } from "react";
import LeadFormPage, { RequiredMark } from "./LeadFormPage";
import PhotoUploader from "@/components/PhotoUploader";

export default function Sell() {
  const [prop, setProp] = useState({ property_type: "house", price: "", location: "", suburb: "", bedrooms: "" });
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
        <input type="number" value={prop.price} onChange={(e) => setProp({ ...prop, price: e.target.value })} data-testid="sell_form-price" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Location / City<RequiredMark /></span>
        <input value={prop.location} onChange={(e) => setProp({ ...prop, location: e.target.value })} data-testid="sell_form-location" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Suburb</span>
        <input value={prop.suburb} onChange={(e) => setProp({ ...prop, suburb: e.target.value })} data-testid="sell_form-suburb" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <PhotoUploader value={photos} onChange={setPhotos} testId="sell_form-photos" />
    </>
  );

  const extraRequired = () =>
    Boolean(prop.property_type && String(prop.price).trim() && prop.location.trim());

  return (
    <LeadFormPage
      source="sell_form"
      kicker="Sell with us"
      title="List your property"
      intro="Tell us about your property — a TREL agent will schedule an appraisal and walk you through our marketing plan. Adding photos speeds up appraisal by 2–3 days."
      extra={extra}
      extraPayload={() => ({ ...prop, photos })}
      extraRequired={extraRequired}
    />
  );
}
