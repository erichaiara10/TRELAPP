import React, { useEffect, useState, useCallback } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import PropertyModal, { serializeProperty } from "@/components/admin/PropertyModal";
import { validateProperty } from "@/components/admin/PropertyModalFields";
import { usePropertyTypes, isPortionScheme } from "@/lib/usePropertyTypes";
import { normalizePhotos } from "@/components/admin/PropertyModalFields";
import PropertiesTable from "@/components/admin/PropertiesTable";
import CsvToolbar from "@/components/admin/CsvToolbar";

const EMPTY = { title:"", listing_type:"sale", property_type:"", price:0, currency:"PGK", bedrooms:0, bathrooms:0, parking:0, area_sqm:0, location:"", suburb:"", province:"", description:"", features:"", photos:[], status:"draft", featured:false, verified:false, allotment_number:"", section_number:"", street_name:"", full_portion_number:"", total_area_ha:"", nearby_landmark:"", address:"", map_coords:"", district:"", local_area:"", tenure_type:"", title_reference:"", property_type_id:"", province_id:"", city_id:"", suburb_id:"", district_id:"", local_area_id:"", street_id:"", owner_name:"", owner_email:"", owner_phone:"", owner_relationship:"OWNER", authority_status:"PENDING", documents:[], duplicate_override:false };

export default function Properties({ scope = "all" } = {}) {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const { types } = usePropertyTypes();

  const validationError = () => validateProperty(modal, isPortionScheme(types, modal?.property_type));

  const load = useCallback(() => {
    const params = { status: "" };
    if (scope === "mine") params.mine = true;
    return api.get("/properties", { params }).then((r) => setItems(r.data));
  }, [scope]);
  useEffect(() => { load(); }, [load]);

  const openNew = () => setModal({ ...EMPTY });
  const openEdit = (p) => setModal({
    ...p,
    features: (p.features || []).join(", "),
    photos: normalizePhotos(p.images),
  });

  const checkDuplicates = async () => {
    const invalid = validationError();
    if (invalid && !["Verify authority before publishing this listing", "Upload an Authority Letter"].includes(invalid)) {
      toast.error(invalid); return;
    }
    setChecking(true);
    try {
      const body = serializeProperty(modal);
      const { data } = await api.post("/properties/duplicate-check", body);
      if (!data.has_possible_duplicates) {
        setModal({ ...modal, duplicate_override: false });
        toast.success("No matching property found");
        return;
      }
      const first = data.candidates[0];
      const allow = window.confirm(
        `Possible duplicate: ${first.title} (${first.confidence}% match).\n\n` +
        `Reasons: ${first.reasons.join(", ")}.\n\n` +
        "Only continue as a separate property if you have checked the existing record."
      );
      setModal({ ...modal, duplicate_override: allow });
      if (allow) toast.warning("Duplicate override recorded for this submission");
    } catch (error) {
      toast.error(formatError(error));
    } finally {
      setChecking(false);
    }
  };

  const save = async () => {
    const invalid = validationError();
    if (invalid) { toast.error(invalid); return; }
    setSaving(true);
    try {
      const body = serializeProperty(modal);
      if (modal.id) await api.put(`/properties/${modal.id}`, body);
      else await api.post("/properties", body);
      toast.success("Saved"); setModal(null); load();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
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
      <CsvToolbar entity="properties" entityLabel="Properties" onImported={load} />
      <PropertiesTable items={items} onEdit={openEdit} onDelete={del} />
      {modal && <PropertyModal modal={modal} setModal={setModal} onSave={save} onDuplicateCheck={checkDuplicates} checking={checking} saving={saving} onClose={() => setModal(null)} />}
    </div>
  );
}
