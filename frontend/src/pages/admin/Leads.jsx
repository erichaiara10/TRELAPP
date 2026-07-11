import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const STATUSES = ["new","contacted","qualified","converted","lost"];
const badge = { new: "bg-blue-100 text-blue-800", contacted:"bg-amber-100 text-amber-800", qualified:"bg-emerald-100 text-emerald-800", converted:"bg-pine-500 text-white", lost:"bg-sand-200 text-ink-700" };

export default function Leads() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const load = useCallback(() => api.get("/leads").then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);
  const setStatus = async (id, status) => { await api.put(`/leads/${id}`, { status }); toast.success("Updated"); load(); };
  const shown = filter ? items.filter((i) => i.status === filter) : items;
  return (
    <div>
      <h1 className="text-2xl font-semibold">Leads</h1>
      <div className="mt-3 flex gap-2 text-sm">
        <button className={`px-3 py-1 rounded-full border border-border ${!filter?"bg-[#0F172A] text-white":""}`} onClick={() => setFilter("")}>All</button>
        {STATUSES.map((s) => <button key={s} className={`px-3 py-1 rounded-full border border-border capitalize ${filter===s?"bg-[#0F172A] text-white":""}`} onClick={() => setFilter(s)} data-testid={`lead-filter-${s}`}>{s}</button>)}
      </div>
      <div className="mt-4 bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr><th className="p-3">Name</th><th className="p-3">Source</th><th className="p-3">Property</th><th className="p-3">Contact</th><th className="p-3">Status</th><th className="p-3">Change</th></tr>
          </thead>
          <tbody>
            {shown.map((l) => (
              <tr key={l.id} className="border-t border-border" data-testid={`lead-row-${l.id}`}>
                <td className="p-3 font-medium">{l.name}</td>
                <td className="p-3 text-xs">{l.source}</td>
                <td className="p-3">{l.property_title || "—"}</td>
                <td className="p-3 text-xs">{l.email}<br />{l.phone}</td>
                <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs capitalize ${badge[l.status]}`}>{l.status}</span></td>
                <td className="p-3">
                  <select value={l.status} onChange={(e) => setStatus(l.id, e.target.value)} data-testid={`lead-status-${l.id}`} className="border border-border rounded px-2 py-1 text-xs">
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
