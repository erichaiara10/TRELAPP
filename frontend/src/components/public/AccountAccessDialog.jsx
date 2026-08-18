import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check, Eye, EyeOff, Mail, Phone, ShieldCheck, X } from "lucide-react";

const BLUE = "#0398FC";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-800">{label}</span>
      {children}
    </label>
  );
}

function PasswordField({ label, value, onChange }) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label}>
      <div className="relative mt-1.5">
        <input
          required
          type={visible ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-11 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
        />
        <button type="button" onClick={() => setVisible(!visible)} className="absolute inset-y-0 right-0 px-3 text-slate-500" aria-label={visible ? "Hide password" : "Show password"}>
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </Field>
  );
}

export default function AccountAccessDialog({ open, initialTab = "login", onClose, selectedService }) {
  const [tab, setTab] = useState(initialTab);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const navigate = useNavigate();

  useEffect(() => setTab(initialTab), [initialTab, open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const submitPreview = (event) => {
    event.preventDefault();
    navigate("/add-property", { state: { previewNotice: true, selectedService } });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" aria-label="TRELPNG account access" data-testid="account-access-dialog">
      <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Close account dialog" />
      <div className="relative z-10 w-full max-w-xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <Link to="/" onClick={onClose} className="text-xl font-bold tracking-tight text-slate-900">TRELPNG</Link>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-500 hover:bg-slate-100" aria-label="Close"><X className="h-5 w-5" /></button>
        </div>

        <div className="grid grid-cols-2 border-b border-slate-200" role="tablist">
          {[{ id: "login", label: "Log In" }, { id: "register", label: "Create New Account" }].map((item) => (
            <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} onClick={() => setTab(item.id)}
              className={`px-5 py-4 text-sm font-semibold ${tab === item.id ? "border-b-[3px] text-sky-600" : "text-slate-500 hover:text-slate-800"}`}
              style={tab === item.id ? { borderColor: BLUE } : undefined}>
              {item.label}
            </button>
          ))}
        </div>

        <form onSubmit={submitPreview} className="max-h-[76vh] overflow-y-auto p-6 sm:p-8">
          <h2 className="text-2xl font-bold text-slate-900">{tab === "login" ? "Welcome back" : "Create your TRELPNG account"}</h2>
          <p className="mt-2 text-sm text-slate-600">
            {tab === "login" ? "One secure login for TREL staff, Property Advertisers and Referral Partners." : "Create your account to continue adding your property."}
          </p>
          {selectedService && <div className="mt-4 rounded-lg bg-sky-50 px-4 py-3 text-sm text-slate-700"><strong>Selected:</strong> {selectedService}</div>}

          <div className="mt-6 space-y-4">
            {tab === "register" && (
              <Field label="Full name *"><input required className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></Field>
            )}
            <Field label="Email address *">
              <div className="relative mt-1.5"><Mail className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input required type="email" className="w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></div>
            </Field>
            {tab === "register" && (
              <Field label="Mobile number *"><div className="relative mt-1.5"><Phone className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input required type="tel" defaultValue="+675 " className="w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></div></Field>
            )}
            <PasswordField label="Password *" value={password} onChange={setPassword} />
            {tab === "register" && <PasswordField label="Confirm password *" value={confirmPassword} onChange={setConfirmPassword} />}
          </div>

          {tab === "login" ? (
            <div className="mt-4 flex items-center justify-between text-sm"><label className="flex items-center gap-2 text-slate-600"><input type="checkbox" /> Remember this device</label><button type="button" className="font-medium text-sky-600">Forgot password?</button></div>
          ) : (
            <div className="mt-5 space-y-3 text-sm text-slate-600">
              <label className="flex items-start gap-2"><input required type="checkbox" className="mt-1" /> <span>I accept the <Link to="/terms" className="text-sky-600">Terms of Use</Link> and <Link to="/privacy" className="text-sky-600">Privacy Policy</Link>.</span></label>
              <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-emerald-800"><ShieldCheck className="h-4 w-4" /> CAPTCHA / anti-robot verification</div>
              <div className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2.5"><Check className="mt-0.5 h-4 w-4 text-emerald-600" /><span>A verification code will be sent to both your email address and mobile number.</span></div>
            </div>
          )}

          <button type="submit" className="mt-6 w-full rounded-lg px-5 py-3 font-semibold text-black hover:brightness-95" style={{ backgroundColor: BLUE }}>
            {tab === "login" ? "Log In Securely" : "Create Account"}
          </button>
          <div className="my-5 flex items-center gap-3 text-xs text-slate-400"><span className="h-px flex-1 bg-slate-200" />OR<span className="h-px flex-1 bg-slate-200" /></div>
          <button type="button" className="w-full rounded-lg border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">Continue with Google</button>
        </form>
      </div>
    </div>
  );
}
