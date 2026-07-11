import React from "react";
import { X } from "lucide-react";

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

export default function PropertyModal({ modal, setModal, onSave, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="prop-modal">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="font-medium">{modal.id ? "Edit property" : "New property"}</div>
          <button onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 grid md:grid-cols-2 gap-3 text-sm">
          {TEXT_FIELDS.map(([k, l]) => (
            <label key={k} className="block col-span-1">
              <span className="text-xs uppercase tracking-widest text-muted-foreground">{l}</span>
              <input value={modal[k] ?? ""} onChange={(e) => setModal({ ...modal, [k]: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" />
            </label>
          ))}
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Listing type</span>
            <select value={modal.listing_type} onChange={(e) => setModal({ ...modal, listing_type: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5">
              <option value="sale">Sale</option><option value="rent">Rent</option>
            </select>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Property type</span>
            <select value={modal.property_type} onChange={(e) => setModal({ ...modal, property_type: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5">
              {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Status</span>
            <select value={modal.status} onChange={(e) => setModal({ ...modal, status: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5">
              {STATUSES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label className="block col-span-2">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Description</span>
            <textarea rows={3} value={modal.description} onChange={(e) => setModal({ ...modal, description: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
          <label className="block col-span-2">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Features (comma)</span>
            <input value={modal.features} onChange={(e) => setModal({ ...modal, features: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
          <label className="block col-span-2">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Image URLs (comma)</span>
            <input value={modal.images} onChange={(e) => setModal({ ...modal, images: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.featured} onChange={(e) => setModal({ ...modal, featured: e.target.checked })} /> Featured</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.verified} onChange={(e) => setModal({ ...modal, verified: e.target.checked })} /> Verified</label>
        </div>
        <div className="p-4 border-t border-border flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 rounded-md border border-border">Cancel</button>
          <button onClick={onSave} data-testid="prop-save" className="px-3 py-2 rounded-md bg-[#0F172A] text-white">Save</button>
        </div>
      </div>
    </div>
  );
}
