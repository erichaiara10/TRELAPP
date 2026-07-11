import React from "react";

const NUMERIC_FIELDS = ["bedrooms", "bathrooms", "parking", "area_sqm", "price"];
const TEXT_FIELDS = [
  ["title","Title"], ["price","Price"], ["location","Location"], ["suburb","Suburb"],
  ["bedrooms","Bedrooms"], ["bathrooms","Bathrooms"], ["parking","Parking"], ["area_sqm","Area (sqm)"],
];
const PROPERTY_TYPES = ["house","apartment","townhouse","land","commercial"];
const STATUSES = ["draft","active","under_offer","sold","leased","withdrawn"];

function toArray(value) {
  if (Array.isArray(value)) return value;
  return String(value || "").split(",").map((s) => s.trim()).filter(Boolean);
}

export function serializeProperty(modal) {
  const out = { ...modal, features: toArray(modal.features), images: toArray(modal.images) };
  NUMERIC_FIELDS.forEach((k) => { out[k] = Number(out[k]) || 0; });
  return out;
}

function TextField({ label, testId, value, onChange }) {
  return (
    <label className="block col-span-1">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}</span>
      <input value={value ?? ""} onChange={onChange} data-testid={testId} className="mt-1 w-full border border-border rounded px-2 py-1.5" />
    </label>
  );
}

function SelectField({ label, testId, value, options, onChange }) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}</span>
      <select value={value} onChange={onChange} data-testid={testId} className="mt-1 w-full border border-border rounded px-2 py-1.5">
        {options.map((o) => (
          typeof o === "string"
            ? <option key={o} value={o}>{o}</option>
            : <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

export default function PropertyModalFields({ modal, setModal }) {
  const set = (k) => (e) => setModal({ ...modal, [k]: e.target.value });
  const setBool = (k) => (e) => setModal({ ...modal, [k]: e.target.checked });
  return (
    <div className="p-4 grid md:grid-cols-2 gap-3 text-sm">
      {TEXT_FIELDS.map(([k, l]) => (
        <TextField key={k} label={l} testId={`property-${k}-input`} value={modal[k]} onChange={set(k)} />
      ))}
      <SelectField label="Listing type" testId="property-listing-type" value={modal.listing_type} onChange={set("listing_type")}
        options={[{ value: "sale", label: "Sale" }, { value: "rent", label: "Rent" }]} />
      <SelectField label="Property type" testId="property-type" value={modal.property_type} onChange={set("property_type")} options={PROPERTY_TYPES} />
      <SelectField label="Status" testId="property-status" value={modal.status} onChange={set("status")} options={STATUSES} />
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Description</span>
        <textarea rows={3} value={modal.description} onChange={set("description")} data-testid="property-description" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Features (comma)</span>
        <input value={modal.features} onChange={set("features")} data-testid="property-features" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Image URLs (comma)</span>
        <input value={modal.images} onChange={set("images")} data-testid="property-images" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.featured} onChange={setBool("featured")} data-testid="property-featured" /> Featured</label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.verified} onChange={setBool("verified")} data-testid="property-verified" /> Verified</label>
    </div>
  );
}
