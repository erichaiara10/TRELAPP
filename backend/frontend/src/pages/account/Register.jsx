import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";

const EMPTY = { name: "", email: "", phone: "", password: "", confirm: "", account_category: "PROPERTY_ADVERTISER", advertiser_relationship_type: "OWNER" };

export default function Register() {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const set = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    if (form.password !== form.confirm) { toast.error("Passwords do not match"); return; }
    setBusy(true);
    try {
      const payload = { ...form }; delete payload.confirm;
      if (payload.account_category !== "PROPERTY_ADVERTISER") payload.advertiser_relationship_type = null;
      await api.post("/auth/register", payload);
      toast.success("Registration complete. Please log in."); navigate("/admin/login");
    } catch (error) { toast.error(formatError(error)); }
    finally { setBusy(false); }
  };
  return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-5">
    <form onSubmit={submit} className="w-full max-w-xl bg-white rounded-2xl border p-7 shadow-sm" data-testid="register-form">
      <Link to="/" className="text-sm text-slate-500">← Back to Home</Link><h1 className="mt-3 text-3xl font-semibold">Register</h1>
      <p className="mt-1 text-sm text-slate-600">Create a Property Advertiser or Referral Partner Account.</p>
      <div className="mt-6 grid sm:grid-cols-2 gap-4">
        <label className="text-sm">Full name<input required value={form.name} onChange={set("name")} className="mt-1 w-full border rounded-lg px-3 py-2.5" /></label>
        <label className="text-sm">Phone number<input required value={form.phone} onChange={set("phone")} className="mt-1 w-full border rounded-lg px-3 py-2.5" /></label>
        <label className="text-sm sm:col-span-2">Email<input required type="email" value={form.email} onChange={set("email")} className="mt-1 w-full border rounded-lg px-3 py-2.5" /></label>
        <label className="text-sm">Password<input required minLength="8" type="password" value={form.password} onChange={set("password")} className="mt-1 w-full border rounded-lg px-3 py-2.5" /></label>
        <label className="text-sm">Confirm password<input required minLength="8" type="password" value={form.confirm} onChange={set("confirm")} className="mt-1 w-full border rounded-lg px-3 py-2.5" /></label>
        <label className="text-sm sm:col-span-2">Account category<select value={form.account_category} onChange={set("account_category")} className="mt-1 w-full border rounded-lg px-3 py-2.5 bg-white"><option value="PROPERTY_ADVERTISER">Property Advertiser Account</option><option value="REFERRAL_PARTNER">Referral Partner Account</option></select></label>
        {form.account_category === "PROPERTY_ADVERTISER" && <label className="text-sm sm:col-span-2">Relationship to property<select value={form.advertiser_relationship_type} onChange={set("advertiser_relationship_type")} className="mt-1 w-full border rounded-lg px-3 py-2.5 bg-white"><option value="OWNER">Owner</option><option value="JOINT_OWNER">Joint Owner</option><option value="AUTHORISED_AGENT">Authorised Real Estate Agent</option><option value="AUTHORISED_REPRESENTATIVE">Authorised Representative of the Owner</option></select></label>}
      </div>
      <button disabled={busy} className="mt-6 w-full rounded-lg bg-[#075C36] text-white py-3 font-semibold disabled:opacity-60">{busy ? "Registering…" : "Register"}</button>
      <p className="mt-4 text-center text-sm">Already registered? <Link to="/admin/login" className="text-[#075C36] font-semibold">Log In</Link></p>
    </form>
  </main>;
}
