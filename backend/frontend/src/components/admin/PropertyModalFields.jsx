import React from "react";
import PhotoUploader from "@/components/PhotoUploader";
import MapCoordsField from "@/components/MapCoordsField";
import LocationPicker from "@/components/LocationPicker";
import PriceInput from "@/components/PriceInput";
import PropertyTypeSelect from "@/components/PropertyTypeSelect";
import FormSection from "@/components/FormSection";
import { sanitizeDigits } from "@/lib/validators";
import { usePropertyTypes, isPortionScheme } from "@/lib/usePropertyTypes";
import { FileText, ScrollText, Wallet, MapPin, ShieldCheck } from "lucide-react";

const NUMERIC_FIELDS = ["bedrooms", "bathrooms", "parking", "area_sqm", "price", "total_area_ha"];
const STATUSES = ["draft", "active", "under_offer", "sold", "leased", "withdrawn"];
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

const LABEL_CLS = "text-xs uppercase tracking-widest text-muted-foreground";
const FIELD_CLS = "mt-1 w-full border border-border rounded px-3 py-2 text-sm bg-white";

function TextField({ label, testId, value, onChange, digitsOnly = false, required = false, placeholder = "", span = "" }) {
  return (
    <label className={`block ${span}`}>
      <span className={LABEL_CLS}>{label}{required && <span className="text-destructive ml-0.5">*</span>}</span>
      <input
        value={value ?? ""}
        placeholder={placeholder}
        onChange={digitsOnly
          ? (e) => onChange({ ...e, target: { ...e.target, value: sanitizeDigits(e.target.value, { notify: true }) } })
          : onChange}
        data-testid={testId}
        className={FIELD_CLS}
      />
    </label>
  );
}

function SelectField({ label, testId, value, options, onChange, span = "" }) {
  return (
    <label className={`block ${span}`}>
      <span className={LABEL_CLS}>{label}</span>
      <select value={value} onChange={onChange} data-testid={testId} className={FIELD_CLS}>
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
  const { types } = usePropertyTypes();
  const isPortion = isPortionScheme(types, modal.property_type);
  const isSale = modal.listing_type === "sale";

  return (
    <div className="p-4 space-y-4 bg-sand-50/50">
      {/* ---- 1. Basics ---- */}
      <FormSection num={1} icon={FileText} title="Basics" hint="Title, description and key stats" testId="prop-section-basics">
        <div className="grid md:grid-cols-2 gap-3 text-sm">
          <TextField label="Title" testId="property-title-input" value={modal.title} onChange={set("title")} required span="md:col-span-2" />
          <label className="block">
            <span className={LABEL_CLS}>Listing type<span className="text-destructive ml-0.5">*</span></span>
            <select value={modal.listing_type} onChange={set("listing_type")} data-testid="property-listing-type" className={FIELD_CLS}>
              {LISTING_TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <TextField label="Bedrooms" testId="property-bedrooms-input" value={modal.bedrooms} onChange={set("bedrooms")} digitsOnly />
          <TextField label="Bathrooms" testId="property-bathrooms-input" value={modal.bathrooms} onChange={set("bathrooms")} digitsOnly />
          <TextField label="Parking" testId="property-parking-input" value={modal.parking} onChange={set("parking")} digitsOnly />
          <TextField label="Area (sqm)" testId="property-area_sqm-input" value={modal.area_sqm} onChange={set("area_sqm")} digitsOnly span="md:col-span-2" />
          <label className="block md:col-span-2">
            <span className={LABEL_CLS}>Description</span>
            <textarea rows={3} value={modal.description || ""} onChange={set("description")} data-testid="property-description" className={FIELD_CLS} />
          </label>
          <label className="block md:col-span-2">
            <span className={LABEL_CLS}>Features (comma-separated)</span>
            <input value={modal.features || ""} onChange={set("features")} data-testid="property-features" className={FIELD_CLS} />
          </label>
        </div>
      </FormSection>

      {/* ---- 2. Legal Description ---- */}
      <FormSection num={2} icon={ScrollText} title="Legal Description" hint="Property identity — cadastral + address components" testId="prop-section-legal">
        <div className="grid md:grid-cols-2 gap-3 text-sm">
          <label className="block">
            <span className={LABEL_CLS}>Property type<span className="text-destructive ml-0.5">*</span></span>
            <div className="mt-1">
              <PropertyTypeSelect admin value={modal.property_type} onChange={(v) => setModal({ ...modal, property_type: v })} testId="property-type" />
            </div>
          </label>
          <label className="block">
            <span className={LABEL_CLS}>Total area (hectares){isSale && <span className="text-destructive ml-0.5">*</span>}</span>
            <input
              type="text"
              inputMode="decimal"
              value={modal.total_area_ha ?? ""}
              onChange={(e) => setModal({ ...modal, total_area_ha: e.target.value.replace(/[^0-9.]/g, "") })}
              placeholder={isPortion ? "e.g. 12.5" : "e.g. 0.0824"}
              data-testid="property-total-area-ha"
              className={FIELD_CLS}
            />
          </label>

          <div className="md:col-span-2">
            <LocationPicker
              value={{ province: modal.province || "", city: modal.location || "", suburb: modal.suburb || "" }}
              onChange={(v) => setModal({ ...modal, province: v.province, location: v.city, suburb: v.suburb })}
              testIdPrefix="property-location"
              required
            />
          </div>

          <TextField label="District (optional)" testId="property-district" value={modal.district} onChange={set("district")} placeholder="e.g. National Capital District" />
          <TextField label="Local area (optional)" testId="property-local-area" value={modal.local_area} onChange={set("local_area")} placeholder="e.g. Waigani" />
          <TextField label="Title reference (optional)" testId="property-title-reference" value={modal.title_reference} onChange={set("title_reference")} placeholder="e.g. Volume/Folio or title number" />
          <SelectField
            label="Tenure type"
            testId="property-tenure-type"
            value={modal.tenure_type || ""}
            onChange={set("tenure_type")}
            options={[
              { value: "", label: "Not specified" },
              { value: "STATE_LEASE", label: "State lease" },
              { value: "FREEHOLD", label: "Freehold" },
              { value: "CUSTOMARY", label: "Customary" },
              { value: "OTHER", label: "Other" },
            ]}
          />

          {!modal.property_type && (
            <div className="md:col-span-2 text-xs text-muted-foreground italic">
              Select a Property Type above to see the relevant legal fields.
            </div>
          )}

          {modal.property_type && !isPortion && (
            <>
              <TextField label="Lot number" testId="property-allotment-number" value={modal.allotment_number} onChange={set("allotment_number")} placeholder="e.g. 15" required />
              <TextField label="Section number" testId="property-section-number" value={modal.section_number} onChange={set("section_number")} placeholder="e.g. 42" required />
              <TextField label="Street name" testId="property-street-name" value={modal.street_name} onChange={set("street_name")} placeholder="e.g. Waigani Drive" required span="md:col-span-2" />
            </>
          )}

          {modal.property_type && isPortion && (
            <TextField label="Portion number" testId="property-full-portion-number" value={modal.full_portion_number} onChange={set("full_portion_number")} placeholder="e.g. 2145C" required span="md:col-span-2" />
          )}
        </div>
      </FormSection>

      {/* ---- 3. Pricing & Valuation ---- */}
      <FormSection num={3} icon={Wallet} title="Pricing & Valuation" hint={isSale ? "Sale price in PGK" : "Monthly rent in PGK"} testId="prop-section-pricing">
        <label className="block text-sm">
          <span className={LABEL_CLS}>Price<span className="text-destructive ml-0.5">*</span></span>
          <div className="mt-1">
            <PriceInput value={modal.price ?? ""} onChange={(v) => setModal({ ...modal, price: v })} testId="property-price" showPreview={false} />
          </div>
        </label>
      </FormSection>

      {/* ---- 4. Location Details ---- */}
      <FormSection num={4} icon={MapPin} title="Location Details" hint="Address, landmark, map coordinates and photos" testId="prop-section-location">
        <div className="grid md:grid-cols-1 gap-3 text-sm">
          <TextField label="Street address" testId="property-address" value={modal.address} onChange={set("address")} placeholder="e.g. 12 Ela Beach Road" />
          <TextField label="Nearby landmark (optional)" testId="property-nearby-landmark" value={modal.nearby_landmark} onChange={set("nearby_landmark")} placeholder={isPortion ? "e.g. 2 km east of Sogeri Plateau road" : "e.g. next to Vision City"} />
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
        </div>
      </FormSection>

      {/* ---- 5. Status & Visibility ---- */}
      <FormSection num={5} icon={ShieldCheck} title="Status & Visibility" hint="Publishing state and homepage placement" testId="prop-section-status">
        <div className="grid md:grid-cols-2 gap-3 text-sm items-end">
          <SelectField label="Status" testId="property-status" value={modal.status} onChange={set("status")} options={STATUSES} />
          <div className="flex flex-wrap gap-4 pb-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!modal.featured} onChange={setBool("featured")} data-testid="property-featured" /> Featured
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!modal.verified} onChange={setBool("verified")} data-testid="property-verified" /> Verified
            </label>
          </div>
        </div>
      </FormSection>
    </div>
  );
}
