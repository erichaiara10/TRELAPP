import React, { useEffect, useState, useCallback } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Trash2, Edit2, KeyRound, X, Plus } from "lucide-react";

const ROLES = ["system_admin","managing_director","sales_manager","sales_agent","leasing_agent","property_manager","marketing_officer"];
const CATEGORY_ROLES = {
  STAFF: ROLES,
  PROPERTY_ADVERTISER: ["property_advertiser"],
  REFERRAL_PARTNER: ["referral_partner"],
};

function EditUserModal({ user, onClose, onSaved }) {
  const [form, setForm] = useState({ name: user.name, email: user.email, role: user.role, phone: user.phone || "", account_category: user.account_category || "UNASSIGNED", status: user.status || "ACTIVE", advertiser_relationship_type: user.advertiser_relationship_type || "OWNER" });
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  const [profileStatus, setProfileStatus] = useState(user.advertiser_profile_status || "PENDING");
  const [identityDocuments, setIdentityDocuments] = useState(user.identity_documents || []);

  const save = async () => {
    setBusy(true);
    try {
      const updates = { ...form };
      delete updates.account_category;
      await api.put(`/users/${user.id}`, updates);
      toast.success("User updated"); onSaved();
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  const resetPassword = async () => {
    if (pwd.length < 6) { toast.error("Password must be at least 6 characters"); return; }
    setBusy(true);
    try {
      await api.put(`/users/${user.id}/password`, { password: pwd });
      toast.success("Password reset");
      setPwd("");
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  const reviewProfile = async (status) => {
    setBusy(true);
    try { await api.put(`/users/${user.id}/advertiser-profile/status`, null, { params:{ status } }); setProfileStatus(status); toast.success(`Advertiser profile ${status.toLowerCase()}`); }
    catch (e) { toast.error(formatError(e)); } finally { setBusy(false); }
  };

  const reviewIdentity = async (id, status) => {
    setBusy(true);
    try { await api.put(`/identity-documents/${id}/status`, null, { params:{ status } }); setIdentityDocuments((items)=>items.map((item)=>item.id===id ? {...item,status} : item)); toast.success(`Government ID ${status.toLowerCase()}`); }
    catch (e) { toast.error(formatError(e)); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
      <div className="bg-white rounded-lg w-full max-w-lg" onClick={(e) => e.stopPropagation()} data-testid="user-edit-modal">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div className="font-medium">Edit user</div>
          <button onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3 text-sm">
          <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Name</span>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="edit-user-name" className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
          <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Email</span>
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="edit-user-email" className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
          <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Role</span>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="edit-user-role" className="mt-1 w-full border border-border rounded px-2 py-1.5">
              {(CATEGORY_ROLES[form.account_category] || [form.role]).map((r) => <option key={r} value={r}>{r}</option>)}
            </select></label>
          <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Account category</span>
            <input value={form.account_category} readOnly className="mt-1 w-full border border-border rounded bg-slate-50 px-2 py-1.5" /></label>
          <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Status</span>
            <select value={form.status} onChange={(e) => setForm({ ...form, status:e.target.value })} className="mt-1 w-full border border-border rounded px-2 py-1.5"><option>ACTIVE</option><option>PENDING</option><option>SUSPENDED</option><option>REJECTED</option></select></label>
          {form.account_category === "PROPERTY_ADVERTISER" && <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Relationship to property</span>
            <select value={form.advertiser_relationship_type} onChange={(e)=>setForm({...form,advertiser_relationship_type:e.target.value})} className="mt-1 w-full border border-border rounded px-2 py-1.5"><option value="OWNER">Owner</option><option value="JOINT_OWNER">Joint Owner</option><option value="AUTHORISED_AGENT">Authorised Agent</option><option value="AUTHORISED_REPRESENTATIVE">Authorised Representative</option></select></label>}
          {form.account_category === "PROPERTY_ADVERTISER" && <div className="border rounded p-3 space-y-2">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Advertiser verification — {profileStatus}</div>
            <div className="flex gap-2"><button onClick={()=>reviewProfile("VERIFIED")} disabled={busy} className="px-2 py-1 rounded bg-pine-600 text-white">Verify profile</button><button onClick={()=>reviewProfile("REJECTED")} disabled={busy} className="px-2 py-1 rounded border text-destructive">Reject</button></div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground pt-2">Government ID</div>
            {identityDocuments.length ? identityDocuments.map((doc)=><div key={doc.id} className="flex justify-between gap-2 items-center text-xs border rounded p-2"><a href={doc.url} target="_blank" rel="noreferrer" className="text-pine-700">{doc.document_type}</a><span>{doc.status}</span><span className="flex gap-1"><button onClick={()=>reviewIdentity(doc.id,"VERIFIED")} disabled={busy} className="text-pine-700">Verify</button><button onClick={()=>reviewIdentity(doc.id,"REJECTED")} disabled={busy} className="text-destructive">Reject</button></span></div>) : <div className="text-xs text-muted-foreground">No government ID submitted.</div>}
          </div>}
          <label className="block"><span className="text-xs uppercase tracking-widest text-muted-foreground">Phone</span>
            <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid="edit-user-phone" className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
          <div className="pt-3 mt-3 border-t border-border">
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-1 flex items-center gap-1"><KeyRound className="w-3.5 h-3.5" /> Reset password</div>
            <div className="flex items-center gap-2">
              <input type="text" placeholder="New password (min 6 chars)" value={pwd} onChange={(e) => setPwd(e.target.value)} data-testid="reset-user-pwd" className="flex-1 border border-border rounded px-2 py-1.5" />
              <button onClick={resetPassword} disabled={busy} data-testid="reset-user-pwd-btn" className="px-3 py-1.5 rounded bg-amber-500 text-white text-sm disabled:opacity-60">Reset</button>
            </div>
            <div className="text-xs text-muted-foreground mt-1">Share the new password with the user securely.</div>
          </div>
        </div>
        <div className="p-4 border-t border-border flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 rounded-md border border-border">Cancel</button>
          <button onClick={save} disabled={busy} data-testid="edit-user-save" className="px-3 py-2 rounded-md bg-[#0F172A] text-white disabled:opacity-60">Save changes</button>
        </div>
      </div>
    </div>
  );
}

export default function Users() {
  const { user: me } = useAuth();
  const [items, setItems] = useState([]);
  const [n, setN] = useState({ email: "", password: "", name: "", role: "sales_agent", account_category: "STAFF", status: "ACTIVE", advertiser_relationship_type: null });
  const [editing, setEditing] = useState(null);
  const load = useCallback(() => api.get("/users").then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try { await api.post("/users", n); toast.success("User created"); setN({ email:"", password:"", name:"", role:"sales_agent", account_category:"STAFF", status:"ACTIVE", advertiser_relationship_type:null }); load(); }
    catch (err) { toast.error(formatError(err)); }
  };
  const del = async (id) => { if (!window.confirm("Delete this user?")) return; try { await api.delete(`/users/${id}`); load(); } catch(e){toast.error(formatError(e));} };
  const isAdmin = me?.role === "system_admin";

  return (
    <div>
      <h1 className="text-2xl font-semibold">User management</h1>
      {isAdmin && (
        <form onSubmit={create} className="mt-4 bg-white border border-border rounded-lg p-4 grid md:grid-cols-7 gap-2" data-testid="user-form">
          <input required placeholder="Name" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} data-testid="user-name" className="border border-border rounded px-3 py-2" />
          <input required type="email" placeholder="Email" value={n.email} onChange={(e) => setN({ ...n, email: e.target.value })} data-testid="user-email" className="border border-border rounded px-3 py-2" />
          <input required type="password" placeholder="Password" value={n.password} onChange={(e) => setN({ ...n, password: e.target.value })} data-testid="user-pwd" className="border border-border rounded px-3 py-2" />
          <input value="STAFF" readOnly aria-label="Account category" className="border border-border rounded bg-slate-50 px-3 py-2" />
          <select value={n.role} onChange={(e) => setN({ ...n, role: e.target.value })} data-testid="user-role" className="border border-border rounded px-3 py-2">
            {CATEGORY_ROLES[n.account_category].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select value={n.status} onChange={(e) => setN({ ...n, status:e.target.value })} className="border border-border rounded px-3 py-2"><option>ACTIVE</option><option>PENDING</option><option>SUSPENDED</option></select>
          {n.account_category === "PROPERTY_ADVERTISER" && <select value={n.advertiser_relationship_type || "OWNER"} onChange={(e)=>setN({...n,advertiser_relationship_type:e.target.value})} className="border border-border rounded px-3 py-2"><option value="OWNER">Owner</option><option value="JOINT_OWNER">Joint Owner</option><option value="AUTHORISED_AGENT">Authorised Agent</option><option value="AUTHORISED_REPRESENTATIVE">Authorised Representative</option></select>}
          <button data-testid="user-add" className="rounded-md bg-[#0F172A] text-white flex items-center justify-center gap-1"><Plus className="w-4 h-4" /> Add user</button>
        </form>
      )}
      <div className="mt-4 bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Category</th><th className="p-3">Role</th><th className="p-3">Status</th><th className="p-3">Phone</th><th className="p-3">Created</th><th className="p-3 text-right">Actions</th></tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id} className="border-t border-border" data-testid={`user-row-${u.id}`}>
                <td className="p-3 font-medium">{u.name}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3 text-xs">{u.account_category || "UNASSIGNED"}</td>
                <td className="p-3"><span className="px-2 py-0.5 rounded-full text-xs bg-sand-100">{u.role}</span></td>
                <td className="p-3 text-xs">{u.status || "ACTIVE"}</td>
                <td className="p-3 text-xs">{u.phone || "—"}</td>
                <td className="p-3 text-xs text-muted-foreground">{(u.created_at||"").slice(0,10)}</td>
                <td className="p-3 text-right whitespace-nowrap">
                  {isAdmin && (
                    <>
                      <button onClick={() => setEditing(u)} data-testid={`edit-user-${u.id}`} className="p-1.5 hover:bg-sand-100 rounded" title="Edit user"><Edit2 className="w-4 h-4" /></button>
                      {u.id !== me.id && <button onClick={() => del(u.id)} data-testid={`del-user-${u.id}`} className="p-1.5 hover:bg-sand-100 rounded text-destructive" title="Delete"><Trash2 className="w-4 h-4" /></button>}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <EditUserModal user={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}
