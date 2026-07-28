import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { MessageSquare, ArrowRightCircle, ExternalLink, Lock, Eye, X } from "lucide-react";
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

/** Prefill a New Property modal from ANY lead — sell-form leads carry a full
 * property payload; contact/inspection leads carry minimal info so most fields
 * arrive blank for the admin to fill in. Description always includes the lead's
 * original message + seller/enquirer contact info. */
function buildPropertyDraftFromLead(lead) {
  const p = lead.payload || {};
  const photos = Array.isArray(p.photos) ? p.photos : [];
  const propertyType = p.property_type || "house";
  const suburb = p.suburb || "";
  const title = [suburb, propertyType].filter(Boolean).join(" ").trim()
    || (p.price ? `${propertyType} listing` : `Property from ${lead.name || "lead"}`);
  const description = [
    lead.message || "",
    lead.name ? `Original contact: ${lead.name}${lead.email ? ` (${lead.email})` : ""}${lead.phone ? ` — ${lead.phone}` : ""}` : "",
    `Source: ${lead.source || "manual"}`,
  ].filter(Boolean).join("\n\n");
  return {
    ...NEW_PROPERTY_DEFAULTS,
    title,
    listing_type: p.listing_type || "sale",
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

function LockedLeadModal({ lead, onClose }) {
  const p = lead.payload || {};
  const photos = Array.isArray(p.photos) ? p.photos : [];
  const rows = [
    ["Full name", lead.name],
    ["Email", lead.email || "—"],
    ["Phone", lead.phone || "—"],
    ["Source", lead.source],
    ["Property type", p.property_type || "—"],
    ["Listing type", p.listing_type || "—"],
    ["Price (PGK)", p.price ? Number(p.price).toLocaleString() : "—"],
    ["Province", p.province || "—"],
    ["City", p.location || "—"],
    ["Suburb", p.suburb || "—"],
    ["Bedrooms", p.bedrooms ?? "—"],
    ["Message", lead.message || "—"],
  ];
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl" data-testid="locked-lead-modal">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="font-medium flex items-center gap-2"><Lock className="w-4 h-4 text-muted-foreground" /> Lead — {lead.name}</div>
          <button onClick={onClose} aria-label="Close" className="p-1 hover:bg-sand-100 rounded"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4">
          <div className="rounded-lg bg-[#0d50e0]/10 border border-[#0d50e0]/30 text-[#0d50e0] p-3 text-sm flex items-start gap-2" data-testid="locked-lead-banner">
            <Lock className="w-4 h-4 mt-0.5 shrink-0" />
            <div className="flex-1">
              <div>This lead has been converted to a Property record{lead.converted_at ? ` on ${new Date(lead.converted_at).toLocaleDateString()}` : ""} and can no longer be edited.</div>
              {lead.property_id && (
                <Link to={`/property/${lead.property_id}`} target="_blank" rel="noreferrer"
                  data-testid="locked-lead-goto-property"
                  className="inline-flex items-center gap-1 mt-2 px-3 py-1.5 rounded-md bg-[#0d50e0] hover:bg-[#0b44c2] text-white text-xs font-medium">
                  <ExternalLink className="w-3.5 h-3.5" /> Go to Property
                </Link>
              )}
            </div>
          </div>
          <dl className="mt-4 grid sm:grid-cols-2 gap-x-4 gap-y-2 text-sm" data-testid="locked-lead-summary">
            {rows.map(([label, value]) => (
              <div key={label} className="border-b border-border/60 py-1.5">
                <dt className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</dt>
                <dd className="text-ink-900 mt-0.5 break-words">{String(value)}</dd>
              </div>
            ))}
          </dl>
          {photos.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">Photos submitted</div>
              <div className="flex flex-wrap gap-2" data-testid="locked-lead-photos">
                {photos.map((ph) => (
                  <a key={ph.id || ph.url} href={`${process.env.REACT_APP_BACKEND_URL}${ph.url}`} target="_blank" rel="noreferrer"
                    className="block w-20 h-20 rounded overflow-hidden border border-border">
                    <img src={`${process.env.REACT_APP_BACKEND_URL}${ph.url}`} alt="" className="w-full h-full object-cover" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="p-4 border-t border-border flex justify-end">
          <button onClick={onClose} data-testid="locked-lead-close" className="px-3 py-2 rounded-md border border-border text-sm">Close</button>
        </div>
      </div>
    </div>
  );
}

export default function Leads() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [commLead, setCommLead] = useState(null);
  const [convertModal, setConvertModal] = useState(null); // property draft including __source_lead_id
  const [savingConvert, setSavingConvert] = useState(false);
  const [viewLead, setViewLead] = useState(null);
  const load = useCallback(() => api.get("/leads").then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const setStatus = async (id, status) => {
    await api.put(`/leads/${id}`, { status });
    toast.success("Updated");
    load();
  };

  const openConvert = (lead) => setConvertModal(buildPropertyDraftFromLead(lead));

  const saveConverted = async () => {
    if (savingConvert) return;
    const leadId = convertModal.__source_lead_id;
    setSavingConvert(true);
    try {
      const body = serializeProperty({ ...convertModal });
      delete body.__source_lead_id;
      // 1) create the property
      const { data: created } = await api.post("/properties", body);
      // 2) mark the lead as converted and link it to the new property (rollback the
      //    property on failure so we don't leave orphaned data)
      try {
        await api.put(`/leads/${leadId}`, {
          status: "converted",
          property_id: created.id,
          property_title: created.title,
        });
      } catch (linkErr) {
        try { await api.delete(`/properties/${created.id}`); } catch { /* best-effort */ }
        throw linkErr;
      }
      toast.success("Property created and lead marked as Converted");
      setConvertModal(null);
      load();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSavingConvert(false); }
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
              const isLocked = Boolean(l.converted_at) || (l.status === "converted" && !!l.property_id);
              const hasLinkedProperty = isLocked && !!l.property_id;
              return (
                <tr key={l.id} className="border-t border-border" data-testid={`lead-row-${l.id}`}>
                  <td className="p-3 font-medium">
                    {l.name}
                    {isLocked && (
                      <div className="mt-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-sand-100 border border-border text-[10px] text-muted-foreground" data-testid={`lead-locked-${l.id}`}>
                        <Lock className="w-3 h-3" /> Converted{l.converted_at ? ` · ${new Date(l.converted_at).toLocaleDateString()}` : ""}
                      </div>
                    )}
                  </td>
                  <td className="p-3 text-xs">{l.source}</td>
                  <td className="p-3">
                    {hasLinkedProperty ? (
                      <Link
                        to={`/property/${l.property_id}`}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`lead-view-property-${l.id}`}
                        className="inline-flex items-center gap-1 text-pine-500 hover:text-pine-600 font-medium"
                      >
                        {l.property_title || "View listing"} <ExternalLink className="w-3.5 h-3.5" />
                      </Link>
                    ) : isLocked ? (
                      <span className="text-xs text-muted-foreground italic">Converted (no linked property)</span>
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
                    {isLocked ? (
                      <span className="text-[11px] text-muted-foreground italic">Read-only</span>
                    ) : (
                      <select value={l.status} onChange={(e) => setStatus(l.id, e.target.value)} data-testid={`lead-status-${l.id}`} className="border border-border rounded px-2 py-1 text-xs">
                        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1 flex-wrap">
                      {isLocked ? (
                        <>
                          {hasLinkedProperty && (
                            <Link to={`/property/${l.property_id}`} target="_blank" rel="noreferrer"
                              data-testid={`lead-goto-property-${l.id}`}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-[#0d50e0] hover:bg-[#0b44c2] text-white text-xs font-medium">
                              <ExternalLink className="w-3.5 h-3.5" /> Go to Property
                            </Link>
                          )}
                          <button onClick={() => setViewLead(l)} data-testid={`lead-view-${l.id}`}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-border text-xs" title="View original lead details">
                            <Eye className="w-3.5 h-3.5" /> View
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => openConvert(l)}
                          data-testid={`lead-convert-${l.id}`}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-pine-500 hover:bg-pine-600 text-white text-xs font-medium"
                          title="Convert this lead into a new property listing (details will be prefilled from the lead)"
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
      {viewLead && <LockedLeadModal lead={viewLead} onClose={() => setViewLead(null)} />}
      {convertModal && (
        <PropertyModal
          modal={convertModal}
          setModal={setConvertModal}
          onSave={saveConverted}
          onClose={() => !savingConvert && setConvertModal(null)}
          saving={savingConvert}
        />
      )}
    </div>
  );
}
