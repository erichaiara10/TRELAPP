import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const COLS = ["new","contacted","qualified","converted","lost"];

export default function Pipeline() {
  const [tab, setTab] = useState("sales");
  const [leads, setLeads] = useState([]);
  const load = () => api.get("/leads").then((r) => setLeads(r.data));
  useEffect(() => { load(); }, []);

  const filtered = leads.filter((l) => tab === "sales"
    ? l.source !== "management_form"
    : l.source === "management_form"
  );
  const move = async (id, status) => { await api.put(`/leads/${id}`, { status }); toast.success("Moved"); load(); };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Pipeline</h1>
      <div className="mt-2 flex gap-2 text-sm">
        {["sales","leasing"].map((t) => (
          <button key={t} onClick={() => setTab(t)} data-testid={`tab-${t}`}
            className={`px-3 py-1 rounded-full border border-border capitalize ${tab===t?"bg-[#0F172A] text-white":""}`}>{t}</button>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        {COLS.map((col) => (
          <div key={col} className="bg-sand-50 rounded-lg p-2" data-testid={`col-${col}`}>
            <div className="text-xs uppercase tracking-widest text-muted-foreground px-1 py-2 flex justify-between">
              <span>{col}</span><span>{filtered.filter((l) => l.status === col).length}</span>
            </div>
            <div className="space-y-2">
              {filtered.filter((l) => l.status === col).map((l) => (
                <div key={l.id} className="bg-white rounded-md border border-border p-2 text-sm" data-testid={`card-${l.id}`}>
                  <div className="font-medium truncate">{l.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{l.property_title || l.source}</div>
                  <div className="mt-2 flex gap-1 flex-wrap">
                    {COLS.filter((s) => s !== col).map((s) => (
                      <button key={s} onClick={() => move(l.id, s)} className="text-[10px] px-1.5 py-0.5 rounded bg-sand-100 hover:bg-sand-200" data-testid={`move-${l.id}-${s}`}>→ {s}</button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
