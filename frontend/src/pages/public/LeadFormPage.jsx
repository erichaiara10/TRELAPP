import React, { useRef, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import HumanVerification from "@/components/HumanVerification";

function Field({ label, ...props }) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}</span>
      <input {...props} className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
    </label>
  );
}
function Area({ label, ...props }) {
  return (
    <label className="block md:col-span-2">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{label}</span>
      <textarea rows={4} {...props} className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
    </label>
  );
}

export function LeadFormPage({ source, title, kicker, intro, extra = null, extraPayload = () => ({}) }) {
  const [form, setForm] = useState({ name: "", email: "", phone: "", message: "" });
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const captchaRef = useRef(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!captchaRef.current?.isValid()) {
      toast.error("Please complete the human verification");
      return;
    }
    setLoading(true);
    try {
      await api.post("/public/leads", {
        source, ...form, payload: extraPayload(), ...captchaRef.current.getPayload(),
      });
      setSent(true);
      toast.success("Thanks! Our team will be in touch shortly.");
    } catch (err) {
      toast.error(formatError(err));
      captchaRef.current?.refresh();
    } finally { setLoading(false); }
  };

  return (
    <div className="container-tight py-14 max-w-3xl">
      <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{kicker}</div>
      <h1 className="font-serif text-4xl sm:text-5xl mt-3">{title}</h1>
      <p className="text-muted-foreground mt-3 max-w-2xl">{intro}</p>

      {sent ? (
        <div className="mt-10 rounded-2xl bg-pine-500 text-white p-8" data-testid={`${source}-success`}>
          <h2 className="font-serif text-2xl">Submission received</h2>
          <p className="mt-2 text-sand-100/90">A dedicated agent from Triumph Real Estate Limited will call you within one business day.</p>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-10 grid md:grid-cols-2 gap-4" data-testid={`${source}-form`}>
          <Field label="Full name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid={`${source}-name`} />
          <Field label="Email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid={`${source}-email`} />
          <Field label="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid={`${source}-phone`} />
          {extra}
          <Area label="Tell us more" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} data-testid={`${source}-message`} />
          <div className="md:col-span-2">
            <HumanVerification ref={captchaRef} />
          </div>
          <div className="md:col-span-2">
            <button disabled={loading} data-testid={`${source}-submit`} className="px-8 py-3 rounded-full bg-pine-500 hover:bg-pine-600 text-white disabled:opacity-60">
              {loading ? "Submitting…" : "Submit"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default LeadFormPage;
