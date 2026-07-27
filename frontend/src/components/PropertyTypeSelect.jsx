import React, { useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { usePropertyTypes } from "@/lib/usePropertyTypes";

/**
 * Shared property-type dropdown. When `admin` is true, adds an inline
 * "+ Add new type" option that opens a small modal to create a new
 * PropertyType (with its legal_scheme). Also renders a delete icon per type
 * (admin-only) so unused ones can be removed.
 *
 * `value` is the selected type NAME (not id). `onChange(name)` fires when the
 * user picks or creates a type.
 */
export default function PropertyTypeSelect({
  value = "",
  onChange,
  admin = false,
  testId = "property-type",
  required = false,
  className = "",
  ...rest
}) {
  const { types, refresh } = usePropertyTypes();
  const [addOpen, setAddOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);

  const handleSelect = (e) => {
    const v = e.target.value;
    if (v === "__add__") {
      setAddOpen(true);
      return;
    }
    onChange?.(v);
  };

  const deleteType = async (t) => {
    try {
      await api.delete(`/property-types/${t.id}`);
      toast.success(`Removed “${t.name}”`);
      await refresh();
      if (value === t.name) onChange?.("");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setPendingDelete(null);
    }
  };

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="flex items-stretch gap-1">
        <select
          value={value || ""}
          onChange={handleSelect}
          required={required}
          data-testid={testId}
          className="flex-1 border border-border rounded-lg px-3 py-2.5 bg-white"
          {...rest}
        >
          <option value="">— Select property type —</option>
          {(types || []).map((t) => (
            <option key={t.id} value={t.name}>{t.name}</option>
          ))}
          {admin && <option value="__add__">＋ Add new type…</option>}
        </select>
      </div>

      {admin && (types || []).length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1" data-testid={`${testId}-manage-list`}>
          {types.map((t) => (
            <span key={t.id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sand-100 border border-border text-[10px] text-muted-foreground">
              {t.name}
              <button
                type="button"
                onClick={() => setPendingDelete(t)}
                data-testid={`${testId}-remove-${t.id}`}
                aria-label={`Remove ${t.name}`}
                className="hover:text-destructive"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {addOpen && (
        <AddTypeModal
          onClose={() => setAddOpen(false)}
          onCreated={async (name) => {
            await refresh();
            onChange?.(name);
            setAddOpen(false);
          }}
        />
      )}
      {pendingDelete && (
        <div className="fixed inset-0 z-[70] bg-black/40 grid place-items-center p-4" onClick={() => setPendingDelete(null)}>
          <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-xl p-5 max-w-sm w-full shadow-2xl">
            <div className="font-medium mb-2">Remove property type?</div>
            <div className="text-sm text-muted-foreground mb-4">“{pendingDelete.name}” will be removed from all dropdowns. Existing properties using this type will keep their value.</div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setPendingDelete(null)} className="px-3 py-1.5 rounded-md border text-sm">Cancel</button>
              <button onClick={() => deleteType(pendingDelete)} data-testid="property-type-delete-confirm" className="px-3 py-1.5 rounded-md bg-destructive text-white text-sm">Remove</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AddTypeModal({ onClose, onCreated }) {
  const [name, setName] = useState("");
  const [scheme, setScheme] = useState("lot_section_street");
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (!name.trim()) { toast.error("Please enter a name"); return; }
    setSaving(true);
    try {
      const { data } = await api.post("/property-types", { name: name.trim(), legal_scheme: scheme, order: 999, is_active: true });
      toast.success("Property type added");
      onCreated?.(data.name);
    } catch (err) {
      toast.error(formatError(err));
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/40 grid place-items-center p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-xl w-full max-w-md shadow-2xl" data-testid="property-type-add-modal">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <div className="font-medium flex items-center gap-2"><Plus className="w-4 h-4 text-[#0d50e0]" /> Add new property type</div>
          <button onClick={onClose} aria-label="Close" className="p-1 hover:bg-sand-100 rounded"><X className="w-4 h-4" /></button>
        </div>
        <form onSubmit={save} className="p-4 space-y-3">
          <label className="block text-sm">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Name<span className="text-destructive ml-0.5">*</span></span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Farm Land"
              data-testid="property-type-add-name"
              autoFocus
              className="mt-1 w-full border border-border rounded px-3 py-2"
            />
          </label>
          <fieldset className="text-sm">
            <legend className="text-xs uppercase tracking-widest text-muted-foreground mb-1">Which legal fields does it use?<span className="text-destructive ml-0.5">*</span></legend>
            <label className="flex items-start gap-2 p-2 rounded-md border border-border cursor-pointer hover:bg-sand-50">
              <input type="radio" name="scheme" value="lot_section_street" checked={scheme === "lot_section_street"} onChange={() => setScheme("lot_section_street")} data-testid="property-type-scheme-lss" className="mt-0.5" />
              <span>
                <span className="font-medium">Lot / Section / Street</span>
                <span className="block text-xs text-muted-foreground">Built property or urban subdivided land.</span>
              </span>
            </label>
            <label className="flex items-start gap-2 p-2 mt-2 rounded-md border border-border cursor-pointer hover:bg-sand-50">
              <input type="radio" name="scheme" value="portion" checked={scheme === "portion"} onChange={() => setScheme("portion")} data-testid="property-type-scheme-portion" className="mt-0.5" />
              <span>
                <span className="font-medium">Portion Number</span>
                <span className="block text-xs text-muted-foreground">Large rural or customary land.</span>
              </span>
            </label>
          </fieldset>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 rounded border text-sm">Cancel</button>
            <button type="submit" disabled={saving} data-testid="property-type-add-save" className="px-3 py-2 rounded bg-[#0d50e0] hover:bg-[#0b44c2] text-white text-sm disabled:opacity-60">
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
