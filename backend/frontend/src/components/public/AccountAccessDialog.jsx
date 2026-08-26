import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Home, X } from "lucide-react";
import { api, formatError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { destinationForUser } from "@/lib/accountRouting";

const TURNSTILE_SITE_KEY =
  process.env.REACT_APP_TURNSTILE_SITE_KEY || "1x00000000000000000000AA";
const TURNSTILE_SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const GOOGLE_SCRIPT_URL = "https://accounts.google.com/gsi/client";

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

function loadGoogleScript() {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.google?.accounts?.oauth2) return Promise.resolve(window.google);
  if (window.__googleIdentityLoading) return window.__googleIdentityLoading;
  window.__googleIdentityLoading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GOOGLE_SCRIPT_URL;
    script.async = true; script.defer = true;
    script.onload = () => resolve(window.google);
    script.onerror = () => reject(new Error("Failed to load Google authentication"));
    document.head.appendChild(script);
  });
  return window.__googleIdentityLoading;
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

export default function AccountAccessDialog({ open, initialTab = "login", onClose, selectedService, next, resetToken = "" }) {
  const [tab, setTab] = useState(initialTab);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [changingEmail, setChangingEmail] = useState(false);
  const [mobile, setMobile] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [resetSignal, setResetSignal] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [resetComplete, setResetComplete] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [googleClientId, setGoogleClientId] = useState("");
  const [googleBusy, setGoogleBusy] = useState(false);
  const [relationship, setRelationship] = useState(selectedService?.relationship || "");
  const { user, login, googleLogin, register, verifyEmailToken, verifyEmailCode, updateUser } = useAuth();
  const navigate = useNavigate();

  useEffect(() => setTab(initialTab), [initialTab, open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);
  useEffect(() => { setError(""); setNotice(""); setGoogleBusy(false); setTurnstileToken(""); setResetSignal((n) => n + 1); }, [tab, open]);
  useEffect(() => {
    if (!open || user?.account_category !== "PROPERTY_ADVERTISER") return;
    if (user.email_verified === false) setTab("verify");
    else if (user.profile_complete === false) setTab("complete");
  }, [open, user]);
  useEffect(() => {
    if (!open || tab !== "verify" || !resetToken) return;
    let active = true;
    setSubmitting(true);
    verifyEmailToken(resetToken).then((result) => {
      if (!active) return;
      setSubmitting(false);
      if (!result.ok) { setError(result.error || "Unable to verify this email address"); return; }
      setNotice("Email verified successfully. Complete your advertiser account below.");
      setTab("complete");
    });
    return () => { active = false; };
  }, [open, tab, resetToken, verifyEmailToken]);
  useEffect(() => { setRelationship(selectedService?.relationship || ""); }, [selectedService?.relationship, open]);
  useEffect(() => {
    if (!open || !["login", "register"].includes(tab)) return;
    Promise.all([loadGoogleScript(), api.get("/auth/google/config")])
      .then(([, response]) => setGoogleClientId(response.data?.enabled ? response.data.client_id : ""))
      .catch(() => setGoogleClientId(""));
  }, [open, tab]);
  if (!open) return null;

  const handleTurnstile = (token) => setTurnstileToken(token || "");

  const continueAuthenticated = (result) => {
    if (result.user?.account_category === "PROPERTY_ADVERTISER" && result.user.email_verified === false) {
      setTab("verify");
      setNotice(`We sent a verification link and six-digit code to ${result.user.email}.`);
      return;
    }
    if (result.user?.account_category === "PROPERTY_ADVERTISER" && result.user.profile_complete === false) {
      setTab("complete");
      setNotice("Complete your advertiser account before continuing to your dashboard.");
      return;
    }
    onClose();
    navigate(destinationForUser(result.user, next), { replace: true, state: { selectedService } });
  };

  const handleGoogle = () => {
    setError(""); setNotice("");
    if (!googleClientId || !window.google?.accounts?.oauth2) {
      setError("Google authentication is temporarily unavailable."); return;
    }
    setGoogleBusy(true);
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: googleClientId,
      scope: "openid email profile",
      callback: async (tokenResponse) => {
        if (!tokenResponse?.access_token) {
          setGoogleBusy(false); setError("Google authentication was cancelled or failed."); return;
        }
        const result = await googleLogin({ access_token: tokenResponse.access_token, mode: tab === "register" ? "register" : "login" });
        setGoogleBusy(false);
        if (!result.ok) { setError(result.error || "Google authentication failed"); return; }
        continueAuthenticated(result);
      },
      error_callback: () => { setGoogleBusy(false); setError("Google authentication was cancelled or failed."); },
    });
    client.requestAccessToken({ prompt: "select_account" });
  };

  const submit = async (event) => {
    event.preventDefault();
    setError(""); setNotice("");
    if (!["reset", "verify", "complete"].includes(tab) && !turnstileToken) { setError("Please complete the human-verification check."); return; }
    if (tab === "verify") {
      if (!/^\d{6}$/.test(verificationCode)) { setError("Enter the six-digit code from your email."); return; }
      setSubmitting(true);
      const result = await verifyEmailCode(verificationCode);
      setSubmitting(false);
      if (!result.ok) { setError(result.error || "Unable to verify this email address"); return; }
      setNotice("Email verified successfully. Complete your advertiser account below.");
      setTab("complete");
      return;
    }
    if (tab === "complete") {
      if (mobile.trim().length < 5) { setError("Enter your mobile number."); return; }
      if (!relationship) { setError("Select your relationship to the property."); return; }
      if (!termsAccepted) { setError("Accept the Terms of Use and Privacy Policy before continuing."); return; }
      setSubmitting(true);
      try {
        await api.put("/auth/complete-advertiser-profile", { phone: mobile.trim(), advertiser_relationship_type: relationship, terms_accepted: true });
        updateUser({ profile_complete: true });
        onClose();
        navigate(destinationForUser({ ...user, profile_complete: true }, next), { replace: true, state: { selectedService } });
      } catch (err) { setError(formatError(err) || "Unable to complete your advertiser account"); }
      finally { setSubmitting(false); }
      return;
    }
    if (tab === "forgot") {
      setSubmitting(true);
      try {
        const { data } = await api.post("/auth/forgot-password", { email: email.trim(), turnstile_token: turnstileToken });
        setNotice(data.message || "If that email is registered, a reset link has been sent.");
      } catch (err) { setError(formatError(err) || "Unable to request a password reset"); }
      finally { setSubmitting(false); setResetSignal((n) => n + 1); setTurnstileToken(""); }
      return;
    }
    if (tab === "reset") {
      if (password !== confirmPassword) { setError("Passwords do not match"); return; }
      if (!resetToken) { setError("This password-reset link is invalid or has expired."); return; }
      setSubmitting(true);
      try {
        await api.post("/auth/reset-password", { token: resetToken, password });
        setResetComplete(true);
        setPassword(""); setConfirmPassword(""); setTab("login");
        navigate("/add-property?auth=login", { replace: true });
      } catch (err) { setError(formatError(err) || "Unable to reset password"); }
      finally { setSubmitting(false); }
      return;
    }
    if (tab === "login") {
      setSubmitting(true);
      const result = await login(email.trim(), password, turnstileToken);
      setSubmitting(false);
      setResetSignal((n) => n + 1); setTurnstileToken("");
      if (!result.ok) { setError(result.error || "Login failed"); return; }
      continueAuthenticated(result);
      return;
    }
    if (password !== confirmPassword) { setError("Passwords do not match"); return; }
    setSubmitting(true);
    try {
      const derivedName = email.trim().split("@")[0].replace(/[._]+/g, " ") || "New user";
      const result = await register({
        name: derivedName,
        email: email.trim(),
        password,
        turnstile_token: turnstileToken,
      });
      setSubmitting(false);
      setResetSignal((n) => n + 1); setTurnstileToken("");
      if (!result.ok) { setError(result.error || "Registration failed"); return; }
      continueAuthenticated(result);
    } catch (err) {
      setSubmitting(false);
      setResetSignal((n) => n + 1); setTurnstileToken("");
      setError(formatError(err) || "Registration failed");
    }
  };

  const resendVerification = async () => {
    setError(""); setSubmitting(true);
    try {
      const { data } = await api.post("/auth/resend-email-verification");
      setNotice(data.message || "A new verification email has been sent.");
    } catch (err) { setError(formatError(err)); }
    finally { setSubmitting(false); }
  };

  const changePendingEmail = async () => {
    setError(""); setSubmitting(true);
    try {
      const { data } = await api.put("/auth/pending-email", { email: email.trim() });
      updateUser({ email: data.email }); setChangingEmail(false);
      setNotice(data.message);
    } catch (err) { setError(formatError(err)); }
    finally { setSubmitting(false); }
  };

  const cannotSubmit = submitting || (!["reset", "verify", "complete"].includes(tab) && !turnstileToken);

  return <div className="fixed inset-0 z-[80] flex items-center justify-center overflow-y-auto bg-slate-800/55 p-4 py-8" role="dialog" aria-modal="true" aria-label="TRELPNG account access" data-testid="account-access-dialog" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <button className="absolute inset-0 cursor-default" onClick={onClose} aria-label="Close account dialog" data-testid="account-access-scrim" />
    <div className="relative z-10 w-full max-w-[600px] rounded-[22px] bg-white px-9 py-8 shadow-2xl sm:px-10" onClick={(event) => event.stopPropagation()}>
      <button type="button" onClick={onClose} className="absolute right-6 top-5 p-2 text-slate-900" aria-label="Close" data-testid="account-access-close"><X className="h-7 w-7" /></button>
      <div className="text-center"><Home className="mx-auto h-14 w-14 fill-[#0398FC] text-[#0398FC]" /><div className="mt-1 text-xl font-bold tracking-wide text-sky-700">TRELPNG</div><h2 className="mt-4 text-3xl font-bold text-slate-900" data-testid="account-access-title">{tab === "login" ? "Welcome Back" : tab === "register" ? "Create Your Account" : tab === "verify" ? "Verify Your Email Address" : tab === "complete" ? "Complete Your Advertiser Account" : tab === "forgot" ? "Forgot Password" : "Reset Password"}</h2></div>
      {!['verify', 'complete'].includes(tab) && <div className="mt-5 grid grid-cols-2 rounded-lg border border-sky-300 bg-sky-50 p-1" role="tablist"><button type="button" role="tab" aria-selected={tab === "login"} data-testid="account-access-tab-login" onClick={() => setTab("login")} className={`rounded-md px-4 py-3 text-base font-semibold ${tab === "login" ? "bg-[#0398FC] text-black" : "text-slate-500"}`}>Log In</button><button type="button" role="tab" aria-selected={tab === "register"} data-testid="account-access-tab-register" onClick={() => setTab("register")} className={`rounded-md px-4 py-3 text-base font-semibold ${tab === "register" ? "bg-[#0398FC] text-black" : "text-slate-500"}`}>Create Account</button></div>}
      <form onSubmit={submit} className="mt-5 space-y-3">
        {(tab === "login" || tab === "register") && <><button type="button" onClick={handleGoogle} disabled={!googleClientId || googleBusy} data-testid="account-access-google" className="flex h-14 w-full items-center justify-center gap-4 rounded-full border border-sky-200 bg-white text-base font-semibold text-slate-800 disabled:opacity-60 disabled:cursor-not-allowed"><span className="text-xl font-bold text-blue-500">G</span> {googleBusy ? "Connecting…" : tab === "register" ? "Sign up with Google" : "Sign in with Google"}</button><div className="flex items-center gap-4 py-1 text-sm text-slate-500"><span className="h-px flex-1 bg-slate-200" />or<span className="h-px flex-1 bg-slate-200" /></div></>}
        {tab === "login" ? <>
          <input required type="email" placeholder="Email address" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="account-access-login-email" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <PasswordInput placeholder="Password" value={password} onChange={setPassword} testId="account-access-login-password" />
          <button type="button" onClick={() => setTab("forgot")} className="block text-sm font-semibold text-sky-700" data-testid="account-access-forgot">Forgot Password?</button>
          <Turnstile onToken={handleTurnstile} resetSignal={resetSignal} />
          {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status" data-testid="account-access-notice">{notice}</p>}
          {resetComplete && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">Password updated. You can now log in.</p>}
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit} data-testid="account-access-login-submit" className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Logging in…" : "Login"}</button>
          <p className="pt-3 text-center text-sm font-semibold text-sky-700">Don’t have an account? <button type="button" onClick={() => setTab("register")}>Create Account</button></p>
        </> : tab === "forgot" ? <>
          <p className="text-sm text-slate-600">Enter your registered email address. We will send you a secure password-reset link.</p>
          <input required type="email" placeholder="Email address" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="account-access-forgot-email" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <Turnstile onToken={handleTurnstile} resetSignal={resetSignal} />
          {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status" data-testid="account-access-notice">{notice}</p>}
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit} className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Sending…" : "Send Reset Link"}</button>
          <button type="button" onClick={() => setTab("login")} className="block w-full text-center text-sm font-semibold text-sky-700">Back to Log In</button>
        </> : tab === "reset" ? <>
          <p className="text-sm text-slate-600">Choose a new password for your TRELPNG account.</p>
          <PasswordInput placeholder="New password" value={password} onChange={setPassword} testId="account-access-reset-password" />
          <PasswordInput placeholder="Confirm new password" value={confirmPassword} onChange={setConfirmPassword} testId="account-access-reset-confirm" />
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit} className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Updating…" : "Update Password"}</button>
        </> : tab === "verify" ? <>
          <p className="text-sm text-slate-600">Click the verification link in your email, or enter the six-digit code below. The link and code expire after 24 hours.</p>
          {notice && <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-700" role="status" data-testid="account-access-notice">{notice}</p>}
          <input required inputMode="numeric" maxLength={6} placeholder="Six-digit verification code" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} data-testid="account-access-verification-code" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-center text-lg tracking-[0.35em] outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={submitting || verificationCode.length !== 6} data-testid="account-access-verify-submit" className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Verifying…" : "Verify Email"}</button>
          <div className="flex flex-wrap justify-center gap-4 pt-1 text-sm font-semibold text-sky-700"><button type="button" disabled={submitting} onClick={resendVerification}>Resend email</button><button type="button" onClick={() => { setEmail(user?.email || ""); setChangingEmail(!changingEmail); }}>Change email address</button></div>
          {changingEmail && <div className="flex gap-2"><input required type="email" placeholder="Correct email address" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="account-access-change-email" className="h-12 min-w-0 flex-1 rounded-lg border border-sky-200 px-3 text-sm" /><button type="button" disabled={submitting || !email.trim()} onClick={changePendingEmail} className="rounded-lg bg-sky-100 px-4 text-sm font-semibold text-sky-800">Update</button></div>}
        </> : tab === "complete" ? <>
          <p className="text-sm text-slate-600">Add the required details below to continue to your advertiser dashboard.</p>
          <input required type="tel" placeholder="Mobile number +675" value={mobile} onChange={(event) => setMobile(event.target.value)} data-testid="account-access-complete-mobile" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <fieldset className="rounded-lg border border-sky-200 p-3" data-testid="account-access-complete-relationship"><legend className="px-1 text-sm text-slate-600">Relationship to the property</legend><div className="grid gap-2 sm:grid-cols-2">{[["OWNER", "Owner"], ["JOINT_OWNER", "Joint owner"], ["AUTHORISED_AGENT", "Authorized agent"], ["AUTHORISED_REPRESENTATIVE", "Authorized representative"]].map(([value, label]) => <label key={value} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${relationship === value ? "border-sky-500 bg-sky-50" : "border-slate-200"}`}><input type="radio" name="advertiser-relationship" value={value} checked={relationship === value} onChange={(event) => setRelationship(event.target.value)} />{label}</label>)}</div></fieldset>
          <label className="flex items-start gap-3 py-1 text-xs text-slate-600"><input required type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} className="mt-0.5 h-4 w-4" data-testid="account-access-complete-terms" /><span>I accept the <Link to="/terms" className="text-sky-700">Terms of Use</Link> and <Link to="/privacy" className="text-sky-700">Privacy Policy</Link>.</span></label>
          {notice && <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-700" role="status" data-testid="account-access-notice">{notice}</p>}
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit || mobile.trim().length < 5 || !relationship || !termsAccepted} data-testid="account-access-complete-submit" className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Completing…" : "Complete Advertiser Account"}</button>
        </> : <>
          <input required type="email" placeholder="Email address" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="account-access-register-email" className="h-14 w-full rounded-lg border border-sky-200 px-4 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100" />
          <PasswordInput placeholder="Password" value={password} onChange={setPassword} testId="account-access-register-password" />
          <PasswordInput placeholder="Confirm password" value={confirmPassword} onChange={setConfirmPassword} testId="account-access-register-confirm" />
          <Turnstile onToken={handleTurnstile} resetSignal={resetSignal} />
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="account-access-error">{error}</p>}
          <button type="submit" disabled={cannotSubmit} data-testid="account-access-register-submit" className="h-14 w-full rounded-full bg-[#0398FC] text-base font-semibold text-black disabled:opacity-60 disabled:cursor-not-allowed">{submitting ? "Creating…" : "Create My Account"}</button>
          <p className="pt-2 text-center text-sm font-semibold text-sky-700">Already have an account? <button type="button" onClick={() => setTab("login")}>Log In</button></p>
        </>}
      </form>
    </div>
  </div>;
}
