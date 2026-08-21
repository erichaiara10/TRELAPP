import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Home, X } from "lucide-react";
import { api, formatError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TURNSTILE_SITE_KEY =
  process.env.REACT_APP_TURNSTILE_SITE_KEY || "1x00000000000000000000AA";
const TURNSTILE_SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

// Route the user based on account_category and preserved intent.
function destinationFor(user, next) {
  if (next) return next;
  const cat = user?.account_category;
  if (cat === "PROPERTY_ADVERTISER") return "/advertiser";
  if (cat === "REFERRAL_PARTNER") return "/referral-partner";
  if (cat === "STAFF") return user?.workspace_path || "/admin";
  // GUEST / unknown → do NOT drop into /admin.
  return user?.workspace_path || "/";
}

function loadTurnstileScript() {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (window.__turnstileLoading) return window.__turnstileLoading;
  window.__turnstileLoading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TURNSTILE_SCRIPT_URL;
    script.async = true; script.defer = true;
    script.onload = () => resolve(window.turnstile);
    script.onerror = () => reject(new Error("Failed to load Cloudflare Turnstile"));
    document.head.appendChild(script);
  });
  return window.__turnstileLoading;
}

function Turnstile({ onToken, resetSignal }) {
  const containerRef = useRef(null);
  const widgetIdRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    loadTurnstileScript().then((ts) => {
      if (!mounted || !containerRef.current || !ts) return;
      widgetIdRef.current = ts.render(containerRef.current, {
        sitekey: TURNSTILE_SITE_KEY,
        callback: (token) => onToken(token),
        "error-callback": () => onToken(""),
        "expired-callback": () => onToken(""),
        theme: "light",
      });
    }).catch(() => onToken(""));
    return () => {
      mounted = false;
      if (widgetIdRef.current && window.turnstile) {
        try { window.turnstile.remove(widgetIdRef.current); } catch (_) {}
        widgetIdRef.current = null;
      }
    };
  }, [onToken]);

  // Reset the widget on tab switch / re-submit.
  useEffect(() => {
    if (widgetIdRef.current && window.turnstile) {
      try { window.turnstile.reset(widgetIdRef.current); } catch (_) {}
    }
  }, [resetSignal]);

  return <div className="min-h-[65px]" data-testid="turnstile-container" ref={containerRef} />;
}

function PasswordInput({ placeholder, value, onChange, testId }) {
  const [visible, setVisible] = useState(false);
  return <div className="relative"><input required type={visible ? "text" : "password"} placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} data-testid={testId} className="h-14 w-full rounded-lg border border-sky-200 px-4 pr-12 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" /><button type="button" onClick={() => setVisible(!visible)} className="absolute inset-y-0 right-0 px-4 text-slate-500" aria-label={visible ? "Hide password" : "Show password"}>{visible ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}</button></div>;
}

export default function AccountAccessDialog({ open, initialTab = "login", onClose, selectedService, next }) {
  const [tab, setTab] = useState(initialTab);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mobile, setMobile] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [resetSignal, setResetSignal] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => setTab(initialTab), [initialTab, open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);
  useEffect(() => { setError(""); setNotice(""); setTurnstileToken(""); setResetSignal((n) => n + 1); }, [tab, open]);
  if (!open) return null;

  const handleTurnstile = (token) => setTurnstileToken(token || "");

  const submit = async (event) => {
    event.preventDefault();
    setError(""); setNotice("");
    if (!turnstileToken) { setError("Please complete the human-verification check."); return; }
    if (tab === "login") {
      setSubmitting(true);
      const result = await login(email.trim(), password, turnstileToken);
      setSubmitting(false);
      setResetSignal((n) => n + 1); setTurnstileToken("");
      if (!result.ok) { setError(result.error || "Login failed"); return; }
      onClose();
      navigate(destinationFor(result.user, next), { replace: true, state: { selectedService } });
      return;
    }
    if (password !== confirmPassword) { setError("Passwords do not match"); return; }
    setSubmitting(true);
    try {
      const derivedName = email.trim().split("@")[0].replace(/[._]+/g, " ") || "New user";
      await api.post("/auth/register", {
        name: derivedName,
        email: email.trim(),
        phone: mobile.trim(),
        password,
        account_category: "PROPERTY_ADVERTISER",
        advertiser_relationship_type: (selectedService && selectedService.relationship) || "OWNER",
        turnstile_token: turnstileToken,
      });
      const result = await login(email.trim(), password, turnstileToken);
      setSubmitting(false);
      setResetSignal((n) => n + 1); setTurnstileToken("");
      if (!result.ok) { setNotice("Account created. Please log in."); setTab("login"); return; }
      onClose();
      navigate(destinationFor(result.user, next), { replace: true, state: { selectedService } });
    } catch (err) {
      setSubmitting(false);
      setResetSignal((n) => n + 1); setTurnstileToken("");
      setError(formatError(err) || "Registration failed");
    }
  };

  const cannotSubmit = submitting || !turnstileToken;

  return <div className="fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-slate-800/55 p-4 py-8" role="dialog" aria-modal="true" aria-label="TRELPNG account access" data-testid="account-access-dialog" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Close account dialog" data-testid="account-access-scrim" />
    <div className="relative z-10 w-full max-w-[600px] rounded-[22px] bg-white px-9 py-8 shadow-2xl sm:px-10" onClick={(event) => event.stopPropagation()}>
      <button type="button" onClick={onClose} className="absolute right-6 top-5 p-2 text-slate-900" aria-label="Close" data-testid="account-access-close"><X className="h-7 w-7" /></button>
      <div className="text-center"><Home className="mx-auto h-14 w-14 fill-[#0398FC] text-[#0398FC]" /><div className="mt-1 text-xl font-bold tracking-wide text-sky-700">TRELPNG</div><h2 className="mt-4 text-3xl font-bold text-slate-900" data-testid="account-access-title">{tab === "login" ? "Welcome Back" : "Create Your Account"}</h2></div>
      <div className="mt-5 grid grid-cols-2 rounded-lg border border-sky-300 bg-sky-50 p-1" role="tablist"><button type="button" role="tab" aria-selected={tab === "login"} data-testid="account-access-tab-login" onClick={() => setTab("login")} className={`rounded-md px-4 py-3 text-base font-semibold ${tab === "login" ? "bg-[#0398FC] text-black" : "text-slate-500"}`}>Log In</button><button type="button" role="tab" aria-selected={tab === "register"} data-testid="account-access-tab-register" onClick={() => setTab("register")} className={`rounded-md px-4 py-3 text-base font-semibold ${tab === "register" ? "bg-[#0398FC] text-black" : "text-slate-500"}`}>Create Account</button></div>
      <form onSubmit={submit} className="mt-5 space-y-3">
        <button type="button" data-testid="account-access-google" className="flex h-14 w-full items-center justify-center gap-4 rounded-full border border-sky-200 bg-white text-base font-semibold text-slate-800"><span className="text-xl font-bold text-blue-500">G</span> Continue with Google</button>
        <div className="flex items-center gap-4 py-1 text-sm text-slate-500"><span className="h-px flex-1 bg-slate-200" />or<span className="h-px flex-1 bg-slate-200" /></div>
        {tab === "login" ? <>
          <input required type="email" placeholder="Email address" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="account-access-login-email" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <PasswordInput placeholder="Password" value={password} onChange={setPassword} testId="account-access-login-password" />
          <button type="button" className="block text-sm font-semibold text-sky-700" data-testid="account-access-forgot">Forgot Password?</button>
          <Turnstile onToken={handleTurnstile} resetSignal={resetSignal} />
          {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status" data-testid="account-access-notice">{notice}</p>}
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit} data-testid="account-access-login-submit" className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Logging in…" : "Login"}</button>
          <p className="pt-3 text-center text-sm font-semibold text-sky-700">Don’t have an account? <button type="button" onClick={() => setTab("register")}>Create Account</button></p>
        </> : <>
          <input required type="email" placeholder="Email address" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="account-access-register-email" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <input required type="tel" placeholder="Mobile number +675" value={mobile} onChange={(event) => setMobile(event.target.value)} data-testid="account-access-register-mobile" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <PasswordInput placeholder="Password" value={password} onChange={setPassword} testId="account-access-register-password" />
          <PasswordInput placeholder="Confirm password" value={confirmPassword} onChange={setConfirmPassword} testId="account-access-register-confirm" />
          <label className="flex items-start gap-3 py-1 text-xs text-slate-600"><input required type="checkbox" className="mt-0.5 h-4 w-4" data-testid="account-access-register-terms" /><span>I accept the <Link to="/terms" className="text-sky-700">Terms of Use</Link> and <Link to="/privacy" className="text-sky-700">Privacy Policy</Link>.</span></label>
          <Turnstile onToken={handleTurnstile} resetSignal={resetSignal} />
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit} data-testid="account-access-register-submit" className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Creating…" : "Create My Account"}</button>
          <p className="pt-2 text-center text-sm font-semibold text-sky-700">Already have an account? <button type="button" onClick={() => setTab("login")}>Log In</button></p>
        </>}
      </form>
    </div>
  </div>;
}
