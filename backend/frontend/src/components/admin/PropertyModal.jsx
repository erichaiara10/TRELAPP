import React from "react";
import { X } from "lucide-react";
import PropertyModalFields, { serializeProperty } from "@/components/admin/PropertyModalFields";

export { serializeProperty };

export default function PropertyModal({ modal, setModal, onSave, onClose, saving = false }) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="prop-modal">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="font-medium">{modal.id ? "Edit property" : "New property"}</div>
          <button onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <PropertyModalFields modal={modal} setModal={setModal} />
        <div className="p-4 border-t border-border flex justify-end gap-2">
          <button onClick={onClose} disabled={saving} className="px-3 py-2 rounded-md border border-border disabled:opacity-60">Cancel</button>
          <button onClick={onSave} disabled={saving} data-testid="prop-save" className="px-3 py-2 rounded-md bg-[#0F172A] text-white disabled:opacity-60">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
