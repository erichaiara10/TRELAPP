import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { MessageSquare, ArrowRightCircle, ExternalLink } from "lucide-react";
import CommunicationsPanel from "@/components/admin/CommunicationsPanel";
import PropertyModal, { serializeProperty } from "@/components/admin/PropertyModal";

const STATUSES = ["new", "contacted", "qualified", "converted", "lost"];
const badge = {
  new: "bg-blue-100 text-blue-800",
  contacted: "bg-amber-100 text-amber-800",
  qualified: "bg-emerald-100 text-emerald-800",
  converted: "bg-pine-500 text-white",
  lost: "bg-sand-200 text-ink-700",
};

const NEW_PROPERTY_DEFAULTS = {
  title: "", listing_type: "sale", property_type: "house", price: 0, currency: "PGK",
  bedrooms: 0, bathrooms: 0, parking: 0, area_sqm: 0,
  province: "", location: "", suburb: "", address: "", map_coords: "",
  description: "", features: "", photos: [],
  status: "active", featured: false, verified: false,
};

/** Prefill a New Property modal from a Sell-form lead's payload + message. */
function buildPropertyDraftFromLead(lead) {
  const p = lead.payload || {};
  const photos = Array.isArray(p.photos) ? p.photos : [];
  const propertyType = p.property_type || "house";
  const suburb = p.suburb || "";
  const title = [suburb, propertyType].filter(Boolean).join(" ").trim() || `Sell submission from ${lead.name || "seller"}`;
  const description = [
    lead.message || "",
    lead.name ? `Original seller: ${lead.name}${lead.email ? ` (${lead.email})` : ""}${lead.phone ? ` — ${lead.phone}` : ""}` : "",
  ].filter(Boolean).join("\n\n");
  return {
    ...NEW_PROPERTY_DEFAULTS,
    title,
    listing_type: "sale",
    property_type: propertyType,
    price: Number(p.price) || 0,
    province: p.province || "",
    location: p.location || "",
    suburb,
    map_coords: p.map_coords || "",
    description,
    photos,
    __source_lead_id: lead.id,
  };
}

export default function Leads() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [commLead, setCommLead] = useState(null);
  const [convertModal, setConvertModal] = useState(null); // property draft including __source_lead_id
  const load = useCallback(() => api.get("/leads").then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const setStatus = async (id, status) => {
    await api.put(`/leads/${id}`, { status });
    toast.success("Updated");
    load();
  };

  const openConvert = (lead) => setConvertModal(buildPropertyDraftFromLead(lead));

  const saveConverted = async () => {
    const leadId = convertModal.__source_lead_id;
    try {
      const body = serializeProperty({ ...convertModal });
      delete body.__source_lead_id;
      // 1) create the property
      const { data: created } = await api.post("/properties", body);
      // 2) mark the lead as converted and link it to the new property
      await api.put(`/leads/${leadId}`, {
        status: "converted",
        property_id: created.id,
        property_title: created.title,
      });
      toast.success("Property created and lead marked as Converted");
      setConvertModal(null);
      load();
    } catch (e) { toast.error(formatError(e)); }
  };

  const shown = filter ? items.filter((i) => i.status === filter) : items;

  return (
    <div>
      <h1 className="text-2xl font-semibold">Leads</h1>
      <div className="mt-3 flex gap-2 text-sm flex-wrap">
        <button className={`px-3 py-1 rounded-full border border-border ${!filter ? "bg-[#0F172A] text-white" : ""}`} onClick={() => setFilter("")}>All</button>
        {STATUSES.map((s) => (
          <button key={s} className={`px-3 py-1 rounded-full border border-border capitalize ${filter === s ? "bg-[#0F172A] text-white" : ""}`} onClick={() => setFilter(s)} data-testid={`lead-filter-${s}`}>{s}</button>
        ))}
      </div>
      <div className="mt-4 bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="p-3">Name</th>
              <th className="p-3">Source</th>
              <th className="p-3">Property / Photos</th>
              <th className="p-3">Contact</th>
              <th className="p-3">Status</th>
              <th className="p-3">Change</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((l) => {
              const isSell = l.source === "sell_form";
              const alreadyConverted = l.status === "converted" && l.property_id;
              return (
                <tr key={l.id} className="border-t border-border" data-testid={`lead-row-${l.id}`}>
                  <td className="p-3 font-medium">{l.name}</td>
                  <td className="p-3 text-xs">{l.source}</td>
                  <td className="p-3">
                    {alreadyConverted ? (
                      <Link
                        to={`/property/${l.property_id}`}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`lead-view-property-${l.id}`}
                        className="inline-flex items-center gap-1 text-pine-500 hover:text-pine-600 font-medium"
                      >
                        {l.property_title || "View listing"} <ExternalLink className="w-3.5 h-3.5" />
                      </Link>
                    ) : (
                      l.property_title || "—"
                    )}
                    {Array.isArray(l.payload?.photos) && l.payload.photos.length > 0 && (
                      <div className="mt-1.5 flex gap-1 flex-wrap" data-testid={`lead-photos-${l.id}`}>
                        {l.payload.photos.map((p) => (
                          <a key={p.id || p.url} href={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} target="_blank" rel="noreferrer"
                            className="block w-10 h-10 rounded overflow-hidden border border-border">
                            <img src={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} alt="" className="w-full h-full object-cover" />
                          </a>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="p-3 text-xs">{l.email}<br />{l.phone}</td>
                  <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs capitalize ${badge[l.status]}`}>{l.status}</span></td>
                  <td className="p-3">
                    <select value={l.status} onChange={(e) => setStatus(l.id, e.target.value)} data-testid={`lead-status-${l.id}`} className="border border-border rounded px-2 py-1 text-xs">
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1">
                      {isSell && !alreadyConverted && (
                        <button
                          onClick={() => openConvert(l)}
                          data-testid={`lead-convert-${l.id}`}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-pine-500 hover:bg-pine-600 text-white text-xs font-medium"
                          title="Convert this sell submission into a new property listing"
                        >
                          <ArrowRightCircle className="w-3.5 h-3.5" /> Convert to Property
                        </button>
                      )}
                      <button onClick={() => setCommLead(l)} data-testid={`lead-history-${l.id}`}
                        className="p-1.5 hover:bg-sand-100 rounded flex items-center gap-1 text-xs text-pine-500" title="Communication history">
                        <MessageSquare className="w-4 h-4" /> Log
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {shown.length === 0 && (
              <tr><td colSpan={7} className="p-6 text-sm text-muted-foreground text-center">No leads in this view.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {commLead && <CommunicationsPanel lead={commLead} onClose={() => setCommLead(null)} />}
      {convertModal && (
        <PropertyModal
          modal={convertModal}
          setModal={setConvertModal}
          onSave={saveConverted}
          onClose={() => setConvertModal(null)}
        />
      )}
    </div>
  );
}
