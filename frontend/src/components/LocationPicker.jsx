import React, { useEffect, useMemo, useState } from "react";
import { MapPin, Plus, Loader2 } from "lucide-react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";

/**
 * Cascading Province → City → Suburb picker.
 *
 * value = { province, city, suburb } (all strings — display names)
 * onChange(value) is fired whenever any of them changes.
 *
 * Users can add a new **Suburb** by picking "➕ Add a new suburb" — the new
 * suburb is POSTed to `/api/locations/suburbs` immediately (source: 'user')
 * and becomes the selected value.
 *
 * `testIdPrefix` (default 'location') controls the data-testids:
 *   {p}-province, {p}-city, {p}-suburb, {p}-new-suburb-input, {p}-new-suburb-save
 *
 * Prop `required` (default false) adds a red asterisk to each label.
 */
export default function LocationPicker({
  value = { province: "", city: "", suburb: "" },
  onChange,
  testIdPrefix = "location",
  required = false,
}) {
  const [provinces, setProvinces] = useState([]);
  const [cities, setCities] = useState([]);
  const [suburbs, setSuburbs] = useState([]);
  const [addingSuburb, setAddingSuburb] = useState(false);
  const [newSuburb, setNewSuburb] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/locations/provinces").then((r) => setProvinces(r.data)).catch(() => {});
  }, []);

  const currentProvince = useMemo(
    () => provinces.find((p) => p.name === value.province) || null,
    [provinces, value.province],
  );
  const currentCity = useMemo(
    () => cities.find((c) => c.name === value.city) || null,
    [cities, value.city],
  );

  useEffect(() => {
    if (!currentProvince) { setCities([]); return; }
    api.get("/locations/cities", { params: { province_id: currentProvince.id } })
      .then((r) => setCities(r.data)).catch(() => setCities([]));
  }, [currentProvince]);

  useEffect(() => {
    if (!currentCity) { setSuburbs([]); return; }
    api.get("/locations/suburbs", { params: { city_id: currentCity.id } })
      .then((r) => setSuburbs(r.data)).catch(() => setSuburbs([]));
  }, [currentCity]);

  const setPatch = (patch) => onChange?.({ ...value, ...patch });

  const onProvinceChange = (e) => {
    const name = e.target.value;
    setPatch({ province: name, city: "", suburb: "" });
    setAddingSuburb(false);
  };
  const onCityChange = (e) => {
    setPatch({ city: e.target.value, suburb: "" });
    setAddingSuburb(false);
  };
  const onSuburbChange = (e) => {
    const v = e.target.value;
    if (v === "__ADD__") { setAddingSuburb(true); setNewSuburb(""); return; }
    setAddingSuburb(false);
    setPatch({ suburb: v });
  };

  const saveNewSuburb = async () => {
    const name = newSuburb.trim();
    if (!name) { toast.error("Please type the new suburb name"); return; }
    if (!currentCity) { toast.error("Please pick a city first"); return; }
    setSaving(true);
    try {
      const { data } = await api.post("/locations/suburbs", { name, city_id: currentCity.id });
      setSuburbs((prev) => {
        // insert or replace by id, keep sorted by name
        const filtered = prev.filter((s) => s.id !== data.id);
        return [...filtered, data].sort((a, b) => a.name.localeCompare(b.name));
      });
      setPatch({ suburb: data.name });
      setAddingSuburb(false);
      setNewSuburb("");
      toast.success(data.source === "user" ? "New suburb added" : "Suburb selected");
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  const req = required ? <span className="text-destructive ml-0.5">*</span> : null;
  const label = (t) => <span className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
    <MapPin className="w-3 h-3 text-pine-500" /> {t}{req}
  </span>;
  const select = "mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white text-sm";

  return (
    <div className="col-span-1 md:col-span-2 grid md:grid-cols-3 gap-3 p-4 rounded-xl bg-sand-50/60 border border-border" data-testid={`${testIdPrefix}-picker`}>
      <div className="md:col-span-3 text-xs uppercase tracking-[0.3em] text-muted-foreground">Location details</div>
      <label className="block">
        {label("Province")}
        <select value={value.province || ""} onChange={onProvinceChange} data-testid={`${testIdPrefix}-province`} className={select}>
          <option value="">— Select a province —</option>
          {provinces.map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}
        </select>
      </label>
      <label className="block">
        {label("City")}
        <select value={value.city || ""} onChange={onCityChange} disabled={!currentProvince} data-testid={`${testIdPrefix}-city`} className={`${select} disabled:opacity-60 disabled:cursor-not-allowed`}>
          <option value="">{currentProvince ? "— Select a city —" : "Pick a province first"}</option>
          {cities.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
        </select>
      </label>
      <label className="block">
        {label("Suburb")}
        <select value={addingSuburb ? "__ADD__" : (value.suburb || "")} onChange={onSuburbChange} disabled={!currentCity} data-testid={`${testIdPrefix}-suburb`} className={`${select} disabled:opacity-60 disabled:cursor-not-allowed`}>
          <option value="">{currentCity ? "— Select a suburb —" : "Pick a city first"}</option>
          {suburbs.map((s) => (
            <option key={s.id} value={s.name}>{s.name}{s.source === "user" ? " • user-added" : ""}</option>
          ))}
          {currentCity && <option value="__ADD__">➕ Add a new suburb…</option>}
        </select>
      </label>
      {addingSuburb && currentCity && (
        <div className="md:col-span-3 flex items-end gap-2 pt-1" data-testid={`${testIdPrefix}-new-suburb-row`}>
          <label className="flex-1 block">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">New suburb name</span>
            <input
              value={newSuburb}
              onChange={(e) => setNewSuburb(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); saveNewSuburb(); } }}
              autoFocus
              placeholder="e.g. Sabama"
              data-testid={`${testIdPrefix}-new-suburb-input`}
              className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white text-sm"
            />
          </label>
          <button type="button" onClick={saveNewSuburb} disabled={saving}
            data-testid={`${testIdPrefix}-new-suburb-save`}
            className="inline-flex items-center gap-1 px-4 py-2.5 rounded-full bg-pine-500 hover:bg-pine-600 text-white text-sm font-medium disabled:opacity-60">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Save
          </button>
          <button type="button" onClick={() => { setAddingSuburb(false); setNewSuburb(""); }}
            data-testid={`${testIdPrefix}-new-suburb-cancel`}
            className="text-xs text-muted-foreground hover:text-ink-900 px-2 py-2.5">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
