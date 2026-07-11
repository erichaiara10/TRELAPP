import React, { useEffect, useState } from "react";
import { api, money, formatError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Edit2, Trash2, X } from "lucide-react";

const empty = { title:"", listing_type:"sale", property_type:"house", price:0, currency:"PGK", bedrooms:0, bathrooms:0, parking:0, area_sqm:0, location:"Port Moresby", suburb:"", description:"", features:"", images:"", status:"active", featured:false, verified:false };

export default function Properties() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const load = () => api.get("/properties", { params: { status: "" } }).then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    const p = { ...modal,
      features: typeof modal.features === "string" ? modal.features.split(",").map((s)=>s.trim()).filter(Boolean) : modal.features,
      images: typeof modal.images === "string" ? modal.images.split(",").map((s)=>s.trim()).filter(Boolean) : modal.images,
      price: Number(modal.price), bedrooms: Number(modal.bedrooms), bathrooms: Number(modal.bathrooms), parking: Number(modal.parking), area_sqm: Number(modal.area_sqm),
    };
    try {
      if (modal.id) await api.put(`/properties/${modal.id}`, p);
      else await api.post("/properties", p);
      toast.success("Saved"); setModal(null); load();
    } catch (e) { toast.error(formatError(e)); }
  };
  const del = async (id) => { if (!window.confirm("Delete?")) return; await api.delete(`/properties/${id}`); load(); };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Properties</h1>
        <button onClick={() => setModal({ ...empty })} data-testid="new-property-btn" className="px-3 py-2 rounded-md bg-[#0F172A] text-white text-sm flex items-center gap-1"><Plus className="w-4 h-4" /> New</button>
      </div>
      <div className="bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr><th className="p-3">Title</th><th className="p-3">Type</th><th className="p-3">Location</th><th className="p-3">Price</th><th className="p-3">Status</th><th className="p-3"></th></tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className="border-t border-border hover:bg-sand-50/50" data-testid={`prop-row-${p.id}`}>
                <td className="p-3 font-medium">{p.title}</td>
                <td className="p-3 capitalize">{p.listing_type} · {p.property_type}</td>
                <td className="p-3">{p.suburb ? `${p.suburb}, ` : ""}{p.location}</td>
                <td className="p-3">{money(p.price, p.currency)}</td>
                <td className="p-3"><span className="px-2 py-0.5 rounded-full text-xs bg-sand-100 capitalize">{p.status}</span></td>
                <td className="p-3 text-right whitespace-nowrap">
                  <button onClick={() => setModal({ ...p, features: (p.features||[]).join(", "), images: (p.images||[]).join(", ") })} data-testid={`edit-${p.id}`} className="p-1.5 hover:bg-sand-100 rounded"><Edit2 className="w-4 h-4" /></button>
                  <button onClick={() => del(p.id)} data-testid={`del-${p.id}`} className="p-1.5 hover:bg-sand-100 rounded text-destructive"><Trash2 className="w-4 h-4" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => setModal(null)}>
          <div className="bg-white rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="prop-modal">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="font-medium">{modal.id ? "Edit property" : "New property"}</div>
              <button onClick={() => setModal(null)}><X className="w-4 h-4" /></button>
            </div>
            <div className="p-4 grid md:grid-cols-2 gap-3 text-sm">
              {[
                ["title","Title"],["price","Price"],["location","Location"],["suburb","Suburb"],
                ["bedrooms","Bedrooms"],["bathrooms","Bathrooms"],["parking","Parking"],["area_sqm","Area (sqm)"],
              ].map(([k,l]) => (
                <label key={k} className="block col-span-1"><span className="text-xs uppercase tracking-widest text-muted-foreground">{l}</span>
                  <input value={modal[k] ?? ""} onChange={(e) => setModal({ ...modal, [k]: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
              ))}
              <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Listing type</span>
                <select value={modal.listing_type} onChange={(e) => setModal({ ...modal, listing_type: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5">
                  <option value="sale">Sale</option><option value="rent">Rent</option></select></label>
              <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Property type</span>
                <select value={modal.property_type} onChange={(e) => setModal({ ...modal, property_type: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5">
                  {["house","apartment","townhouse","land","commercial"].map((t)=><option key={t} value={t}>{t}</option>)}</select></label>
              <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Status</span>
                <select value={modal.status} onChange={(e) => setModal({ ...modal, status: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5">
                  {["draft","active","under_offer","sold","leased","withdrawn"].map((t)=><option key={t} value={t}>{t}</option>)}</select></label>
              <label className="block col-span-2"><span className="text-xs uppercase tracking-widest text-muted-foreground">Description</span>
                <textarea rows={3} value={modal.description} onChange={(e) => setModal({ ...modal, description: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
              <label className="block col-span-2"><span className="text-xs uppercase tracking-widest text-muted-foreground">Features (comma)</span>
                <input value={modal.features} onChange={(e) => setModal({ ...modal, features: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
              <label className="block col-span-2"><span className="text-xs uppercase tracking-widest text-muted-foreground">Image URLs (comma)</span>
                <input value={modal.images} onChange={(e) => setModal({ ...modal, images: e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.featured} onChange={(e) => setModal({ ...modal, featured: e.target.checked })} /> Featured</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={!!modal.verified} onChange={(e) => setModal({ ...modal, verified: e.target.checked })} /> Verified</label>
            </div>
            <div className="p-4 border-t border-border flex justify-end gap-2">
              <button onClick={() => setModal(null)} className="px-3 py-2 rounded-md border border-border">Cancel</button>
              <button onClick={save} data-testid="prop-save" className="px-3 py-2 rounded-md bg-[#0F172A] text-white">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
