import React from "react";
import PhotoUploader from "@/components/PhotoUploader";
import MapCoordsField from "@/components/MapCoordsField";
import LocationPicker from "@/components/LocationPicker";
import PriceInput from "@/components/PriceInput";
import { sanitizeDigits } from "@/lib/validators";

const NUMERIC_FIELDS = ["bedrooms", "bathrooms", "parking", "area_sqm", "price", "total_area_ha"];
const TEXT_FIELDS = [
  ["title","Title"],
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

function TextField({ label, testId, value, onChange, digitsOnly = false, required = false }) {
  return (
    <label className="block col-span-1">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}{required && <span className="text-destructive ml-0.5">*</span>}</span>
      <input value={value ?? ""} onChange={digitsOnly ? (e) => onChange({ ...e, target: { ...e.target, value: sanitizeDigits(e.target.value, { notify: true }) } }) : onChange} data-testid={testId} className="mt-1 w-full border border-border rounded px-2 py-1.5" />
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
      <TextField label="Title" testId="property-title-input" value={modal.title} onChange={set("title")} required />
      <label className="block col-span-1">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Price<span className="text-destructive ml-0.5">*</span></span>
        <div className="mt-1"><PriceInput value={modal.price ?? ""} onChange={(v) => setModal({ ...modal, price: v })} testId="property-price" showPreview={false} /></div>
      </label>
      {TEXT_FIELDS.filter(([k]) => k !== "title").map(([k, l]) => (
        <TextField key={k} label={l} testId={`property-${k}-input`} value={modal[k]} onChange={set(k)} digitsOnly />
      ))}
      <SelectField label="Listing type" testId="property-listing-type" value={modal.listing_type} onChange={set("listing_type")}
        options={LISTING_TYPES} />
      <SelectField label="Property type" testId="property-type" value={modal.property_type} onChange={set("property_type")} options={PROPERTY_TYPES} />
      <SelectField label="Status" testId="property-status" value={modal.status} onChange={set("status")} options={STATUSES} />
      <LocationPicker
        value={{ province: modal.province || "", city: modal.location || "", suburb: modal.suburb || "" }}
        onChange={(v) => setModal({ ...modal, province: v.province, location: v.city, suburb: v.suburb })}
        testIdPrefix="property-location"
        required
      />
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Description{modal.land_category === "large_portion" ? <span className="text-destructive ml-0.5">*</span> : null}</span>
        <textarea rows={3} value={modal.description} onChange={set("description")} data-testid="property-description" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Features (comma)</span>
        <input value={modal.features} onChange={set("features")} data-testid="property-features" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>

      {/* ---- Legal & Location details (Feb 22, 2026) ---- */}
      <div className="col-span-2 pt-2 mt-1 border-t border-border">
        <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Legal & location details</div>
        <div className="grid md:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Land category{modal.listing_type === "sale" ? <span className="text-destructive ml-0.5">*</span> : null}</span>
            <select value={modal.land_category || ""} onChange={set("land_category")} data-testid="property-land-category" className="mt-1 w-full border border-border rounded px-2 py-1.5">
              <option value="">— Not specified —</option>
              <option value="large_portion">Large Portion</option>
              <option value="subdivided_town_land">Subdivided Town Land</option>
            </select>
          </label>
          {modal.listing_type === "sale" && (
            <label className="block">
              <span className="text-xs uppercase tracking-widest text-muted-foreground">Total area (hectares)<span className="text-destructive ml-0.5">*</span></span>
              <input type="text" inputMode="decimal" value={modal.total_area_ha ?? ""}
                onChange={(e) => setModal({ ...modal, total_area_ha: e.target.value.replace(/[^0-9.]/g, "") })}
                placeholder="e.g. 0.0824" data-testid="property-total-area-ha" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
            </label>
          )}
          {modal.land_category === "large_portion" && (
            <label className="block col-span-2">
              <span className="text-xs uppercase tracking-widest text-muted-foreground">Full portion number<span className="text-destructive ml-0.5">*</span></span>
              <input value={modal.full_portion_number ?? ""} onChange={set("full_portion_number")} data-testid="property-full-portion-number" placeholder="e.g. 2145C" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
            </label>
          )}
          {modal.land_category === "subdivided_town_land" && (
            <>
              <label className="block">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Allotment number<span className="text-destructive ml-0.5">*</span></span>
                <input value={modal.allotment_number ?? ""} onChange={set("allotment_number")} data-testid="property-allotment-number" placeholder="e.g. 15" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
              </label>
              <label className="block">
                <span className="text-xs uppercase tracking-widest text-muted-foreground">Section number<span className="text-destructive ml-0.5">*</span></span>
                <input value={modal.section_number ?? ""} onChange={set("section_number")} data-testid="property-section-number" placeholder="e.g. 42" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
              </label>
            </>
          )}
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Street name (optional)</span>
            <input value={modal.street_name ?? ""} onChange={set("street_name")} data-testid="property-street-name" placeholder="e.g. Waigani Drive" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Nearby landmark (optional)</span>
            <input value={modal.nearby_landmark ?? ""} onChange={set("nearby_landmark")} data-testid="property-nearby-landmark" placeholder="e.g. next to Vision City" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
        </div>
      </div>

      <label className="block col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Street address</span>
        <input value={modal.address ?? ""} onChange={set("address")} data-testid="property-address" placeholder="e.g. 12 Ela Beach Road" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
      </label>
      <MapCoordsField
        label="Google Maps location"
        value={modal.map_coords ?? ""}
        onChange={(v) => setModal({ ...modal, map_coords: v })}
        testId="property-map-coords"
        city={modal.location}
        suburb={modal.suburb}
        province={modal.province}
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
