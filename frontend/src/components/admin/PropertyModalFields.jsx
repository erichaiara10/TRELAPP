import React from "react";
import PhotoUploader from "@/components/PhotoUploader";
import MapCoordsField from "@/components/MapCoordsField";
import LocationPicker from "@/components/LocationPicker";

const NUMERIC_FIELDS = ["bedrooms", "bathrooms", "parking", "area_sqm", "price"];
const TEXT_FIELDS = [
  ["title","Title"], ["price","Price"],
  ["bedrooms","Bedrooms"], ["bathrooms","Bathrooms"], ["parking","Parking"], ["area_sqm","Area (sqm)"],
];
const PROPERTY_TYPES = ["house","apartment","townhouse","land","commercial"];
const STATUSES = ["draft","active","under_offer","sold","leased","withdrawn"];
const LISTING_TYPES = [{ value: "sale", label: "Sale" }, { value: "rent", label: "Rent" }];

function toArray(value) {
  if (Array.isArray(value)) return value;
  return String(value || "").split(",").map((s) => s.trim()).filter(Boolean);
}

export function normalizePhotos(v) {
  if (!v) return [];
  if (Array.isArray(v)) {
    return v.map((x) => (typeof x === "string" ? { url: x, name: "external" } : x)).filter((p) => p && p.url);
  }
  return toArray(v).map((u) => ({ url: u, name: "external" }));
}

export function photosToUrls(photos) {
  return (photos || []).map((p) => {
    if (!p) return "";
    if (typeof p === "string") return p;
    if (!p.url) return "";
    return p.url.startsWith("http") ? p.url : `${process.env.REACT_APP_BACKEND_URL}${p.url}`;
  }).filter(Boolean);
}

export function serializeProperty(modal) {
  const out = { ...modal, features: toArray(modal.features), images: photosToUrls(modal.photos) };
  delete out.photos;
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
  const setPhotos = (photos) => setModal({ ...modal, photos });
  return (
    <div className="p-4 grid md:grid-cols-2 gap-3 text-sm">
      {TEXT_FIELDS.map(([k, l]) => (
        <TextField key={k} label={l} testId={`property-${k}-input`} value={modal[k]} onChange={set(k)} />
      ))}
      <SelectField label="Listing type" testId="property-listing-type" value={modal.listing_type} onChange={set("listing_type")}
        options={LISTING_TYPES} />
      <SelectField label="Property type" testId="property-type" value={modal.property_type} onChange={set("property_type")} options={PROPERTY_TYPES} />
      <SelectField label="Status" testId="property-status" value={modal.status} onChange={set("status")} options={STATUSES} />
      <LocationPicker
        value={{ province: modal.province || "", city: modal.location || "", suburb: modal.suburb || "" }}
        onChange={(v) => setModal({ ...modal, province: v.province, location: v.city, suburb: v.suburb })}
        testIdPrefix="property-location"
      />
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Description</span>
        <textarea rows={3} value={modal.description} onChange={set("description")} data-testid="property-description" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Features (comma)</span>
        <input value={modal.features} onChange={set("features")} data-testid="property-features" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Street address</span>
        <input value={modal.address ?? ""} onChange={set("address")} data-testid="property-address" placeholder="e.g. 12 Ela Beach Road" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <MapCoordsField
        label="Google Maps location"
        value={modal.map_coords ?? ""}
        onChange={(v) => setModal({ ...modal, map_coords: v })}
        testId="property-map-coords"
      />
      <PhotoUploader
        value={modal.photos || []}
        onChange={setPhotos}
        max={20}
        allowUrls
        allowCover
        label="Property images"
        testId="property-photos"
      />
      <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.featured} onChange={setBool("featured")} data-testid="property-featured" /> Featured</label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.verified} onChange={setBool("verified")} data-testid="property-verified" /> Verified</label>
    </div>
  );
}
