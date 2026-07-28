import React, { useEffect, useState, useCallback } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import PropertyModal, { serializeProperty } from "@/components/admin/PropertyModal";
import { normalizePhotos } from "@/components/admin/PropertyModalFields";
import PropertiesTable from "@/components/admin/PropertiesTable";

const EMPTY = { title:"", listing_type:"sale", property_type:"", price:0, currency:"PGK", bedrooms:0, bathrooms:0, parking:0, area_sqm:0, location:"", suburb:"", province:"", description:"", features:"", photos:[], status:"active", featured:false, verified:false, allotment_number:"", section_number:"", street_name:"", full_portion_number:"", total_area_ha:"", nearby_landmark:"", address:"", map_coords:"" };

export default function Properties() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);

  const load = useCallback(() => api.get("/properties", { params: { status: "" } }).then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => setModal({ ...EMPTY });
  const openEdit = (p) => setModal({
    ...p,
    features: (p.features || []).join(", "),
    photos: normalizePhotos(p.images),
  });

  const save = async () => {
    try {
      const body = serializeProperty(modal);
      if (modal.id) await api.put(`/properties/${modal.id}`, body);
      else await api.post("/properties", body);
      toast.success("Saved"); setModal(null); load();
    } catch (e) { toast.error(formatError(e)); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete?")) return;
    await api.delete(`/properties/${id}`); load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Properties</h1>
        <button onClick={openNew} data-testid="new-property-btn" className="px-3 py-2 rounded-md bg-[#0F172A] text-white text-sm flex items-center gap-1">
          <Plus className="w-4 h-4" /> New
        </button>
      </div>
      <PropertiesTable items={items} onEdit={openEdit} onDelete={del} />
      {modal && <PropertyModal modal={modal} setModal={setModal} onSave={save} onClose={() => setModal(null)} />}
    </div>
  );
}
