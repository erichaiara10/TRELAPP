import React, { useCallback, useEffect, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, X, Loader2, Search } from "lucide-react";

const CUSTOMER_TYPES = ["buyer", "seller", "tenant", "landlord", "corporate"];

const EMPTY = { name: "", email: "", phone: "", customer_type: "buyer", company: "", notes: "", source: "manual" };

function CustomerModal({ modal, setModal, onSave, onClose, saving }) {
  const set = (k) => (e) => setModal({ ...modal, [k]: e.target.value });
  const field = "mt-1 w-full border border-border rounded px-3 py-2 text-sm";
  const label = "text-xs uppercase tracking-widest text-muted-foreground";
  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={() => !saving && onClose()}>
      <div className="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="customer-modal">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="font-medium">{modal.id ? "Edit customer" : "New customer"}</div>
          <button onClick={onClose} aria-label="Close" disabled={saving}><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 grid md:grid-cols-2 gap-3">
          <label className="block md:col-span-2">
            <span className={label}>Full name <span className="text-destructive">*</span></span>
            <input value={modal.name} onChange={set("name")} placeholder="e.g. Jane Doe" data-testid="customer-name" className={field} required />
          </label>
          <label className="block">
            <span className={label}>Email</span>
            <input type="email" value={modal.email || ""} onChange={set("email")} placeholder="you@example.com" data-testid="customer-email" className={field} />
          </label>
          <label className="block">
            <span className={label}>Phone</span>
            <input value={modal.phone || ""} onChange={set("phone")} placeholder="+675 …" data-testid="customer-phone" className={field} />
          </label>
          <label className="block">
            <span className={label}>Type <span className="text-destructive">*</span></span>
            <select value={modal.customer_type} onChange={set("customer_type")} data-testid="customer-type" className={field}>
              {CUSTOMER_TYPES.map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
            </select>
          </label>
          <label className="block">
            <span className={label}>Company (optional)</span>
            <input value={modal.company || ""} onChange={set("company")} placeholder="e.g. Acme Ltd" data-testid="customer-company" className={field} />
          </label>
          <label className="block md:col-span-2">
            <span className={label}>Notes</span>
            <textarea rows={3} value={modal.notes || ""} onChange={set("notes")} data-testid="customer-notes" className={field} />
          </label>
        </div>
        <div className="p-4 border-t border-border flex justify-end gap-2">
          <button onClick={onClose} disabled={saving} className="px-3 py-2 rounded-md border border-border disabled:opacity-60">Cancel</button>
          <button onClick={onSave} disabled={saving || !modal.name.trim()} data-testid="customer-save"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-pine-500 hover:bg-pine-600 text-white disabled:opacity-60">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

const typeBadge = {
  buyer: "bg-blue-100 text-blue-800",
  seller: "bg-emerald-100 text-emerald-800",
  tenant: "bg-purple-100 text-purple-800",
  landlord: "bg-amber-100 text-amber-800",
  corporate: "bg-pine-500 text-white",
};

export default function Customers() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/customers"); setItems(data); }
    catch (e) { toast.error(formatError(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => setModal({ ...EMPTY });
  const openEdit = (c) => setModal({ ...EMPTY, ...c });

  const save = async () => {
    if (!modal.name.trim()) { toast.error("Name is required"); return; }
    setSaving(true);
    try {
      const payload = {
        name: modal.name.trim(),
        email: (modal.email || "").trim() || null,
        phone: (modal.phone || "").trim() || null,
        customer_type: modal.customer_type,
        company: (modal.company || "").trim() || null,
        notes: modal.notes || "",
        source: modal.source || "manual",
      };
      if (modal.id) await api.put(`/customers/${modal.id}`, payload);
      else await api.post("/customers", payload);
      toast.success(modal.id ? "Customer updated" : "Customer added");
      setModal(null);
      await load();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  const del = async (c) => {
    if (!window.confirm(`Delete customer "${c.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/customers/${c.id}`);
      toast.success("Customer deleted");
      await load();
    } catch (e) { toast.error(formatError(e)); }
  };

  const shown = q.trim()
    ? items.filter((c) => [c.name, c.email, c.phone, c.company].some((f) => (f || "").toLowerCase().includes(q.toLowerCase())))
    : items;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h1 className="text-2xl font-semibold">Customers</h1>
          <p className="text-sm text-muted-foreground">CRM records created from public forms and manual entry.</p>
        </div>
        <button onClick={openNew} data-testid="customer-add-btn"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-pine-500 hover:bg-pine-600 text-white text-sm font-medium">
          <Plus className="w-4 h-4" /> Add Customer
        </button>
      </div>

      <div className="mb-3 flex items-center gap-2 rounded-md border border-border bg-white px-3 max-w-md">
        <Search className="w-4 h-4 text-muted-foreground" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, email, phone…" data-testid="customer-search"
          className="flex-1 py-2 text-sm outline-none bg-transparent" />
      </div>

      <div className="bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="p-3">Name</th>
              <th className="p-3">Type</th>
              <th className="p-3">Email</th>
              <th className="p-3">Phone</th>
              <th className="p-3">Company</th>
              <th className="p-3">Source</th>
              <th className="p-3">Created</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.id} className="border-t border-border hover:bg-sand-50/50" data-testid={`cust-row-${c.id}`}>
                <td className="p-3 font-medium">{c.name}</td>
                <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs capitalize ${typeBadge[c.customer_type] || "bg-sand-100"}`}>{c.customer_type}</span></td>
                <td className="p-3">{c.email || "—"}</td>
                <td className="p-3">{c.phone || "—"}</td>
                <td className="p-3">{c.company || "—"}</td>
                <td className="p-3 text-xs">{c.source}</td>
                <td className="p-3 text-xs text-muted-foreground">{(c.created_at || "").slice(0,10)}</td>
                <td className="p-3">
                  <div className="flex items-center gap-1 justify-end">
                    <button onClick={() => openEdit(c)} title="Edit" data-testid={`customer-edit-${c.id}`}
                      className="p-1.5 rounded hover:bg-sand-100 text-muted-foreground hover:text-ink-900">
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button onClick={() => del(c)} title="Delete" data-testid={`customer-delete-${c.id}`}
                      className="p-1.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={8} className="p-6 text-sm text-muted-foreground text-center">
                {q.trim() ? "No customers match your search." : "No customers yet. Click 'Add Customer' to create one."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && <CustomerModal modal={modal} setModal={setModal} onSave={save} onClose={() => !saving && setModal(null)} saving={saving} />}
    </div>
  );
}
