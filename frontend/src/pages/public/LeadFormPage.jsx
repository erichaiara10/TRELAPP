import React, { useRef, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle2 } from "lucide-react";
import HumanVerification from "@/components/HumanVerification";

const REQUIRED_ERROR = "Please fill in all required fields marked with a red asterisk before submitting.";
const SUCCESS_MESSAGE = "You have successfully submitted your form. An agent will attend to you shortly.";

function RequiredMark() {
  return <span className="text-destructive ml-0.5" aria-label="required">*</span>;
}

function Field({ label, required, ...props }) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">
        {label}{required && <RequiredMark />}
      </span>
      <input {...props} className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
    </label>
  );
}
function Area({ label, required, ...props }) {
  return (
    <label className="block md:col-span-2">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">
        {label}{required && <RequiredMark />}
      </span>
      <textarea rows={4} {...props} className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
    </label>
  );
}

/**
 * Shared public form container.
 * Displays optional hero (image + kicker + heading + intro) above the form,
 * then the standard [name, email, phone, ...extra, message] grid,
 * then a clean success card on submit.
 */
export function LeadFormPage({
  source, title, kicker, intro, heroImage,
  extra = null, extraPayload = () => ({}), extraRequired = () => true,
}) {
  const [form, setForm] = useState({ name: "", email: "", phone: "", message: "" });
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const captchaRef = useRef(null);

  const submit = async (e) => {
    e.preventDefault();
    const missingBase = !form.name.trim() || !form.email.trim() || !form.phone.trim();
    if (missingBase || !extraRequired()) {
      toast.error(REQUIRED_ERROR);
      return;
    }
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
      toast.success("Submission received");
    } catch (err) {
      toast.error(formatError(err));
      captchaRef.current?.refresh();
    } finally { setLoading(false); }
  };

  return (
    <div className="container-tight py-14 max-w-3xl">
      {heroImage && (
        <div className="rounded-2xl overflow-hidden mb-8 aspect-[3/1] bg-sand-100 border border-border" data-testid={`${source}-hero-image`}>
          <img src={heroImage} alt="" className="w-full h-full object-cover" />
        </div>
      )}
      <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{kicker}</div>
      <h1 className="font-serif text-4xl sm:text-5xl mt-3">{title}</h1>
      {intro && <p className="text-muted-foreground mt-3 max-w-2xl whitespace-pre-line">{intro}</p>}

      {sent ? (
        <div className="mt-10 rounded-2xl bg-pine-500 text-white p-8" data-testid={`${source}-success`}>
          <div className="flex items-start gap-3">
            <CheckCircle2 className="w-8 h-8 shrink-0 mt-0.5" />
            <div>
              <h2 className="font-serif text-2xl">Thank you!</h2>
              <p className="mt-2 text-sand-100 text-lg" data-testid={`${source}-success-message`}>
                {SUCCESS_MESSAGE}
              </p>
              <button
                onClick={() => { setSent(false); setForm({ name: "", email: "", phone: "", message: "" }); captchaRef.current?.refresh(); }}
                data-testid={`${source}-success-again`}
                className="mt-6 inline-flex items-center gap-2 px-5 py-2 rounded-full bg-white text-pine-500 font-medium hover:bg-sand-50"
              >
                Submit another
              </button>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} noValidate className="mt-10 grid md:grid-cols-2 gap-4" data-testid={`${source}-form`}>
          <Field label="Full name" required placeholder="e.g. Jane Doe" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid={`${source}-name`} />
          <Field label="Email" required type="email" placeholder="you@example.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid={`${source}-email`} />
          <Field label="Phone" required placeholder="+675 …" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} data-testid={`${source}-phone`} />
          {extra}
          <Area label="Tell us more" placeholder="Share any details that will help us respond faster." value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} data-testid={`${source}-message`} />
          <div className="md:col-span-2">
            <HumanVerification ref={captchaRef} />
          </div>
          <div className="md:col-span-2">
            <button disabled={loading} data-testid={`${source}-submit`} className="px-8 py-3 rounded-full bg-pine-500 hover:bg-pine-600 text-white disabled:opacity-60">
              {loading ? "Submitting…" : "Submit"}
            </button>
            <p className="text-xs text-muted-foreground mt-2"><span className="text-destructive">*</span> indicates a required field</p>
          </div>
        </form>
      )}
    </div>
  );
}

export default LeadFormPage;
export { RequiredMark };
