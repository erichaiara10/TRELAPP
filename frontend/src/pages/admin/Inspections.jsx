import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const STATUSES = ["requested","scheduled","completed","cancelled"];

export default function Inspections() {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get("/inspections").then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);
  const setStatus = async (id, status) => { await api.put(`/inspections/${id}`, { status }); toast.success("Updated"); load(); };
  const setFeedback = async (id, feedback) => { await api.put(`/inspections/${id}`, { feedback }); toast.success("Feedback saved"); };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Inspections</h1>
      <div className="mt-4 space-y-2">
        {items.map((i) => (
          <div key={i.id} className="bg-white rounded-lg border border-border p-4 grid md:grid-cols-6 gap-3 items-center text-sm" data-testid={`insp-${i.id}`}>
            <div className="md:col-span-2">
              <div className="font-medium">{i.property_title}</div>
              <div className="text-xs text-muted-foreground">{i.customer_name} · {i.customer_phone || i.customer_email}</div>
            </div>
            <div className="text-xs">Preferred: {i.preferred_date || "—"}</div>
            <select value={i.status} onChange={(e) => setStatus(i.id, e.target.value)} data-testid={`insp-status-${i.id}`} className="border border-border rounded px-2 py-1">
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <input placeholder="Feedback…" defaultValue={i.feedback} onBlur={(e) => e.target.value !== (i.feedback||"") && setFeedback(i.id, e.target.value)} data-testid={`insp-fb-${i.id}`} className="border border-border rounded px-2 py-1 md:col-span-2" />
          </div>
        ))}
        {items.length === 0 && <div className="text-sm text-muted-foreground">No inspection requests yet.</div>}
      </div>
    </div>
  );
}
