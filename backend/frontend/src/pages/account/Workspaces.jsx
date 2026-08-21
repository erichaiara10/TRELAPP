import React, { useEffect, useState } from "react";
import { api, formatError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import Properties from "@/pages/admin/Properties";

function Header({ title }) {
  const { user, logout } = useAuth();
  return <header className="flex justify-between items-center border-b p-5 bg-white">
    <div><div className="text-xs tracking-[0.25em] text-muted-foreground">TRELPNG</div><h1 className="text-2xl font-semibold">{title}</h1></div>
    <div className="text-right text-sm"><div>{user?.name}</div><button className="text-pine-700" onClick={logout}>Sign out</button></div>
  </header>;
}

export function AdvertiserWorkspace() {
  const [documents, setDocuments] = useState([]);
  const [type, setType] = useState("NID_CARD");
  const load = () => api.get("/identity-documents/mine").then((r) => setDocuments(r.data));
  useEffect(() => { load(); }, []);
  const upload = async (file) => {
    if (!file) return;
    const form = new FormData(); form.append("document_type", type); form.append("file", file);
    try { await api.post("/identity-documents/upload", form); toast.success("ID submitted for verification"); load(); }
    catch (e) { toast.error(formatError(e)); }
  };
  return <div className="min-h-screen bg-sand-50"><Header title="Property Advertiser Workspace" />
    <main className="max-w-3xl mx-auto p-6 space-y-5">
      <section className="bg-white border rounded-xl p-5"><h2 className="font-medium">Identity verification</h2>
        <p className="text-sm text-muted-foreground mt-1">Submit one government-issued ID: Passport, Driver Licence or NID Card.</p>
        <div className="flex gap-2 mt-4"><select value={type} onChange={(e) => setType(e.target.value)} className="border rounded px-3 py-2">
          <option value="PASSPORT">Passport</option><option value="DRIVER_LICENCE">Driver Licence</option><option value="NID_CARD">NID Card</option>
        </select><input type="file" accept=".pdf,image/jpeg,image/png,image/webp" onChange={(e) => upload(e.target.files?.[0])} /></div>
        <div className="mt-4 space-y-2">{documents.map((d) => <div key={d.id} className="border rounded p-2 text-sm">{d.document_type} — {d.status}</div>)}</div>
      </section>
      <p className="text-sm text-muted-foreground">Property creation is accepted only after the advertiser profile and one government ID are verified.</p>
      <section className="bg-white border rounded-xl p-5"><Properties scope="mine" /></section>
    </main></div>;
}

export function ReferralPartnerWorkspace() {
  const [form, setForm] = useState({ owner_name: "", owner_phone: "", owner_email: "", source_relationship: "OWNER", direct_from_owner: true, notes: "" });
  const [items, setItems] = useState([]);
  const load = () => api.get("/referrals/mine").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);
  const submit = async (e) => { e.preventDefault(); try { await api.post("/referrals", form); toast.success("Referral submitted"); setForm({ ...form, owner_name:"", owner_phone:"", owner_email:"", notes:"" }); load(); } catch (err) { toast.error(formatError(err)); } };
  return <div className="min-h-screen bg-sand-50"><Header title="Referral Partner Workspace" /><main className="max-w-3xl mx-auto p-6">
    <form onSubmit={submit} className="bg-white border rounded-xl p-5 space-y-3"><h2 className="font-medium">Refer a property directly from its owner</h2>
      <input required placeholder="Owner name" value={form.owner_name} onChange={(e)=>setForm({...form,owner_name:e.target.value})} className="w-full border rounded px-3 py-2" />
      <input placeholder="Owner phone" value={form.owner_phone} onChange={(e)=>setForm({...form,owner_phone:e.target.value})} className="w-full border rounded px-3 py-2" />
      <input type="email" placeholder="Owner email" value={form.owner_email} onChange={(e)=>setForm({...form,owner_email:e.target.value})} className="w-full border rounded px-3 py-2" />
      <select value={form.source_relationship} onChange={(e)=>setForm({...form,source_relationship:e.target.value})} className="w-full border rounded px-3 py-2"><option value="OWNER">Owner</option><option value="JOINT_OWNER">Joint owner</option></select>
      <label className="flex gap-2 text-sm"><input required type="checkbox" checked={form.direct_from_owner} onChange={(e)=>setForm({...form,direct_from_owner:e.target.checked})} /> I confirm this referral came directly from the owner and not through another agent.</label>
      <textarea placeholder="Notes" value={form.notes} onChange={(e)=>setForm({...form,notes:e.target.value})} className="w-full border rounded px-3 py-2" />
      <button className="bg-[#0F172A] text-white rounded px-4 py-2">Submit referral</button>
    </form>
    <div className="mt-5 space-y-2">{items.map((r)=><div key={r.id} className="bg-white border rounded p-3 text-sm">{r.owner_name} — {r.status}</div>)}</div>
  </main></div>;
}
