import React, { useEffect, useState, useCallback } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { X, MessageSquare, Phone, Mail, StickyNote, Send, Trash2 } from "lucide-react";

const KIND_ICONS = { call: Phone, email: Mail, whatsapp: MessageSquare, note: StickyNote, meeting: MessageSquare, sms: MessageSquare };
const KINDS = ["note", "call", "email", "whatsapp", "sms", "meeting"];
const DIRECTIONS = ["outbound", "inbound", "internal"];

/**
 * Communication history panel — reusable for both leads and customers.
 *
 * Pass either `lead={...}` (legacy) OR `parent={{ type: 'lead'|'customer', id, name, subtitle }}`.
 */
export default function CommunicationsPanel({ lead, parent, onClose }) {
  const p = parent || (lead ? { type: "lead", id: lead.id, name: lead.name, subtitle: lead.email || lead.phone || "—" } : null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ kind: "note", direction: "outbound", subject: "", body: "" });

  const base = p ? `/${p.type === "customer" ? "customers" : "leads"}/${p.id}/communications` : null;

  const load = useCallback(async () => {
    if (!base) return;
    setLoading(true);
    try {
      const { data } = await api.get(base);
      setItems(data);
    } catch (e) { toast.error(formatError(e)); }
    finally { setLoading(false); }
  }, [base]);

  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.body.trim()) { toast.error("Please enter a message"); return; }
    try {
      await api.post(base, form);
      setForm({ ...form, subject: "", body: "" });
      load();
      toast.success("Logged");
    } catch (e) { toast.error(formatError(e)); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this entry?")) return;
    try { await api.delete(`/communications/${id}`); load(); }
    catch (e) { toast.error(formatError(e)); }
  };

  if (!p) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex justify-end" onClick={onClose}>
      <div className="bg-white w-full max-w-lg h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()} data-testid="comm-panel">
        <div className="p-4 border-b border-border sticky top-0 bg-white z-10 flex items-center justify-between">
          <div>
            <div className="font-medium">Communication history</div>
            <div className="text-xs text-muted-foreground truncate">
              <span className="uppercase tracking-widest mr-1.5">{p.type}</span>· {p.name} · {p.subtitle}
            </div>
          </div>
          <button onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-4 space-y-3">
          {loading && <div className="text-xs text-muted-foreground">Loading…</div>}
          {!loading && items.length === 0 && <div className="text-xs text-muted-foreground">No communications logged yet. Add the first one below.</div>}
          {items.map((c) => {
            const Icon = KIND_ICONS[c.kind] || StickyNote;
            const dirClr = c.direction === "inbound" ? "border-l-blue-500" : c.direction === "internal" ? "border-l-sand-300" : "border-l-pine-500";
            return (
              <div key={c.id} className={`bg-sand-50 border border-border border-l-4 ${dirClr} rounded-md p-3`} data-testid={`comm-${c.id}`}>
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <Icon className="w-3.5 h-3.5" />
                    <span className="uppercase tracking-widest">{c.kind}</span>
                    <span>·</span>
                    <span className="capitalize">{c.direction}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{(c.created_at || "").replace("T", " ").slice(0, 16)}</span>
                    <button onClick={() => del(c.id)} data-testid={`comm-del-${c.id}`} className="p-1 hover:bg-white rounded text-destructive" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
                {c.subject && <div className="mt-1.5 font-medium text-sm">{c.subject}</div>}
                <div className="mt-1 text-sm whitespace-pre-wrap">{c.body}</div>
                {c.agent_name && <div className="mt-1.5 text-xs text-muted-foreground">by {c.agent_name}</div>}
              </div>
            );
          })}
        </div>

        <form onSubmit={submit} className="p-4 border-t border-border sticky bottom-0 bg-white space-y-2" data-testid="comm-form">
          <div className="grid grid-cols-2 gap-2">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} data-testid="comm-kind" className="border border-border rounded px-2 py-1.5 text-sm">
              {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <select value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value })} data-testid="comm-direction" className="border border-border rounded px-2 py-1.5 text-sm">
              {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <input placeholder="Subject (optional)" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} data-testid="comm-subject" className="w-full border border-border rounded px-2 py-1.5 text-sm" />
          <textarea rows={3} placeholder="What was discussed / said?" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="comm-body" className="w-full border border-border rounded px-2 py-1.5 text-sm" />
          <button data-testid="comm-submit" className="w-full py-2 rounded-md bg-[#0F172A] text-white text-sm flex items-center justify-center gap-2">
            <Send className="w-4 h-4" /> Log entry
          </button>
        </form>
      </div>
    </div>
  );
}
