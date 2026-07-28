import React, { useEffect, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { MapPin, Plus, Pencil, Trash2, Loader2, ChevronRight } from "lucide-react";

/**
 * Admin master-detail: Provinces | Cities | Suburbs
 * Click a province → its cities load in the middle column.
 * Click a city → its suburbs load in the right column.
 */
export default function Locations() {
  const [provinces, setProvinces] = useState([]);
  const [cities, setCities] = useState([]);
  const [suburbs, setSuburbs] = useState([]);
  const [selP, setSelP] = useState(null);
  const [selC, setSelC] = useState(null);
  const [loadingP, setLoadingP] = useState(true);
  const [loadingC, setLoadingC] = useState(false);
  const [loadingS, setLoadingS] = useState(false);

  const loadProvinces = async () => {
    setLoadingP(true);
    try { const { data } = await api.get("/locations/provinces"); setProvinces(data); }
    finally { setLoadingP(false); }
  };
  const loadCities = async (pid) => {
    if (!pid) { setCities([]); return; }
    setLoadingC(true);
    try { const { data } = await api.get("/locations/cities", { params: { province_id: pid } }); setCities(data); }
    finally { setLoadingC(false); }
  };
  const loadSuburbs = async (cid) => {
    if (!cid) { setSuburbs([]); return; }
    setLoadingS(true);
    try { const { data } = await api.get("/locations/suburbs", { params: { city_id: cid } }); setSuburbs(data); }
    finally { setLoadingS(false); }
  };

  useEffect(() => { loadProvinces(); }, []);
  useEffect(() => { loadCities(selP?.id); setSelC(null); setSuburbs([]); }, [selP]);
  useEffect(() => { loadSuburbs(selC?.id); }, [selC]);

  // ---- add / rename / delete handlers -------------------------------------
  const addProvince = async () => {
    const name = window.prompt("New province name")?.trim();
    if (!name) return;
    try { await api.post("/admin/locations/provinces", { name }); await loadProvinces(); toast.success("Province added"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const renameProvince = async (p) => {
    const name = window.prompt("Rename province", p.name)?.trim();
    if (!name || name === p.name) return;
    try { await api.put(`/admin/locations/provinces/${p.id}`, { name }); await loadProvinces();
      if (selP?.id === p.id) setSelP({ ...p, name });
      toast.success("Province renamed"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const deleteProvince = async (p) => {
    if (!window.confirm(`Delete "${p.name}" and ALL its cities and suburbs?`)) return;
    try { await api.delete(`/admin/locations/provinces/${p.id}`); await loadProvinces();
      if (selP?.id === p.id) { setSelP(null); setCities([]); setSelC(null); setSuburbs([]); }
      toast.success("Province deleted"); }
    catch (e) { toast.error(formatError(e)); }
  };

  const addCity = async () => {
    if (!selP) { toast.error("Pick a province first"); return; }
    const name = window.prompt(`New city in ${selP.name}`)?.trim();
    if (!name) return;
    try { await api.post("/admin/locations/cities", { name, province_id: selP.id }); await loadCities(selP.id); toast.success("City added"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const renameCity = async (c) => {
    const name = window.prompt("Rename city", c.name)?.trim();
    if (!name || name === c.name) return;
    try { await api.put(`/admin/locations/cities/${c.id}`, { name }); await loadCities(selP.id);
      if (selC?.id === c.id) setSelC({ ...c, name });
      toast.success("City renamed"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const deleteCity = async (c) => {
    if (!window.confirm(`Delete "${c.name}" and ALL its suburbs?`)) return;
    try { await api.delete(`/admin/locations/cities/${c.id}`); await loadCities(selP.id);
      if (selC?.id === c.id) { setSelC(null); setSuburbs([]); }
      toast.success("City deleted"); }
    catch (e) { toast.error(formatError(e)); }
  };

  const addSuburb = async () => {
    if (!selC) { toast.error("Pick a city first"); return; }
    const name = window.prompt(`New suburb in ${selC.name}`)?.trim();
    if (!name) return;
    try { await api.post("/admin/locations/suburbs", { name, city_id: selC.id }); await loadSuburbs(selC.id); toast.success("Suburb added"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const renameSuburb = async (s) => {
    const name = window.prompt("Rename suburb", s.name)?.trim();
    if (!name || name === s.name) return;
    try { await api.put(`/admin/locations/suburbs/${s.id}`, { name }); await loadSuburbs(selC.id); toast.success("Suburb renamed"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const deleteSuburb = async (s) => {
    if (!window.confirm(`Delete "${s.name}"?`)) return;
    try { await api.delete(`/admin/locations/suburbs/${s.id}`); await loadSuburbs(selC.id); toast.success("Suburb deleted"); }
    catch (e) { toast.error(formatError(e)); }
  };

  const Column = ({ title, addLabel, onAdd, addDisabled, loading, children, testId }) => (
    <div className="border border-border rounded-xl bg-white flex flex-col min-h-[420px]" data-testid={testId}>
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="font-medium text-sm">{title}</div>
        <button
          type="button" onClick={onAdd} disabled={addDisabled}
          data-testid={`${testId}-add`}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-pine-500 hover:bg-pine-600 text-white text-xs disabled:opacity-40 disabled:cursor-not-allowed">
          <Plus className="w-3.5 h-3.5" /> {addLabel}
        </button>
      </div>
      <div className="flex-1 overflow-auto p-2" data-testid={`${testId}-list`}>
        {loading ? (
          <div className="p-4 text-sm text-muted-foreground flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
        ) : children}
      </div>
    </div>
  );

  const rowCls = (active) => `w-full text-left px-3 py-2 rounded-md text-sm flex items-center justify-between gap-1 group ${active ? "bg-pine-500 text-white" : "hover:bg-sand-50"}`;

  return (
    <div>
      <div className="flex items-center gap-2">
        <MapPin className="w-5 h-5 text-pine-500" />
        <h1 className="text-2xl font-semibold">Locations</h1>
      </div>
      <p className="text-sm text-muted-foreground mt-1">Manage the Province → City → Suburb hierarchy used across forms and search. Suburbs added by users via public forms appear here with a "user-added" badge.</p>

      <div className="mt-5 grid md:grid-cols-3 gap-4">
        <Column title="Provinces" addLabel="Add province" onAdd={addProvince} loading={loadingP} testId="provinces-col">
          {provinces.length === 0 && <div className="p-4 text-xs text-muted-foreground">No provinces yet.</div>}
          {provinces.map((p) => (
            <div key={p.id} className="flex items-center">
              <button onClick={() => setSelP(p)} className={rowCls(selP?.id === p.id)} data-testid={`province-${p.id}`}>
                <span className="truncate flex-1">{p.name}</span>
                {selP?.id === p.id && <ChevronRight className="w-4 h-4 shrink-0" />}
              </button>
              <div className="flex items-center gap-0.5 pr-2">
                <button onClick={() => renameProvince(p)} title="Rename" className="p-1 rounded hover:bg-sand-100 text-muted-foreground hover:text-ink-900" data-testid={`province-rename-${p.id}`}><Pencil className="w-3.5 h-3.5" /></button>
                <button onClick={() => deleteProvince(p)} title="Delete" className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" data-testid={`province-delete-${p.id}`}><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          ))}
        </Column>

        <Column title={selP ? `Cities in ${selP.name}` : "Cities"} addLabel="Add city" onAdd={addCity} addDisabled={!selP} loading={loadingC} testId="cities-col">
          {!selP && <div className="p-4 text-xs text-muted-foreground">Pick a province.</div>}
          {selP && cities.length === 0 && <div className="p-4 text-xs text-muted-foreground">No cities in this province yet.</div>}
          {cities.map((c) => (
            <div key={c.id} className="flex items-center">
              <button onClick={() => setSelC(c)} className={rowCls(selC?.id === c.id)} data-testid={`city-${c.id}`}>
                <span className="truncate flex-1">{c.name}</span>
                {selC?.id === c.id && <ChevronRight className="w-4 h-4 shrink-0" />}
              </button>
              <div className="flex items-center gap-0.5 pr-2">
                <button onClick={() => renameCity(c)} title="Rename" className="p-1 rounded hover:bg-sand-100 text-muted-foreground hover:text-ink-900" data-testid={`city-rename-${c.id}`}><Pencil className="w-3.5 h-3.5" /></button>
                <button onClick={() => deleteCity(c)} title="Delete" className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" data-testid={`city-delete-${c.id}`}><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          ))}
        </Column>

        <Column title={selC ? `Suburbs in ${selC.name}` : "Suburbs"} addLabel="Add suburb" onAdd={addSuburb} addDisabled={!selC} loading={loadingS} testId="suburbs-col">
          {!selC && <div className="p-4 text-xs text-muted-foreground">Pick a city.</div>}
          {selC && suburbs.length === 0 && <div className="p-4 text-xs text-muted-foreground">No suburbs in this city yet.</div>}
          {suburbs.map((s) => (
            <div key={s.id} className="flex items-center">
              <div className={rowCls(false)} data-testid={`suburb-${s.id}`}>
                <span className="truncate flex-1">{s.name}</span>
                {s.source === "user" && (
                  <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 rounded-full bg-terracotta-50 text-terracotta-600" data-testid={`suburb-${s.id}-user-badge`}>user</span>
                )}
              </div>
              <div className="flex items-center gap-0.5 pr-2">
                <button onClick={() => renameSuburb(s)} title="Rename" className="p-1 rounded hover:bg-sand-100 text-muted-foreground hover:text-ink-900" data-testid={`suburb-rename-${s.id}`}><Pencil className="w-3.5 h-3.5" /></button>
                <button onClick={() => deleteSuburb(s)} title="Delete" className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive" data-testid={`suburb-delete-${s.id}`}><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          ))}
        </Column>
      </div>
    </div>
  );
}
