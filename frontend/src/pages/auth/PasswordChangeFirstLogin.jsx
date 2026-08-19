import React, { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Home, ShieldCheck, ArrowLeft, CheckCircle2, XCircle } from "lucide-react";
import { api, formatError } from "@/lib/api";

// Client-side mirror of backend rules — informational only. Server is source of truth.
const rules = [
  { id: "length", label: "At least 12 characters", test: (v) => v.length >= 12 },
  { id: "lower", label: "One lowercase letter (a-z)", test: (v) => /[a-z]/.test(v) },
  { id: "upper", label: "One uppercase letter (A-Z)", test: (v) => /[A-Z]/.test(v) },
  { id: "digit", label: "One digit (0-9)", test: (v) => /\d/.test(v) },
  { id: "special", label: "One special character", test: (v) => /[^A-Za-z0-9]/.test(v) },
];

function StrengthChecklist({ password }) {
  return (
    <ul className="mt-2 grid gap-1.5 rounded-lg border border-sky-100 bg-sky-50/40 p-3 text-xs" data-testid="password-rules">
      {rules.map((rule) => {
        const ok = rule.test(password);
        return (
          <li key={rule.id} className={`flex items-center gap-2 ${ok ? "text-emerald-700" : "text-slate-600"}`} data-testid={`rule-${rule.id}-${ok ? "ok" : "fail"}`}>
            {ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4 text-slate-300" />}
            <span>{rule.label}</span>
          </li>
        );
      })}
    </ul>
  );
}

function PasswordField({ id, label, value, onChange, autoFocus }) {
  const [visible, setVisible] = useState(false);
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-widest text-slate-600">{label}</span>
      <div className="relative mt-1">
        <input
          required
          autoFocus={autoFocus}
          autoComplete="new-password"
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          data-testid={id}
          className="h-12 w-full rounded-lg border border-sky-200 px-4 pr-12 text-sm outline-none focus:border-[#0398FC] focus:ring-2 focus:ring-sky-100"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          data-testid={`${id}-toggle`}
          className="absolute inset-y-0 right-0 px-3 text-slate-500"
        >
          {visible ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
        </button>
      </div>
    </label>
  );
}

export default function PasswordChangeFirstLogin() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = location.state?.changeToken;
  const email = location.state?.email;

  const [newPwd, setNewPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const allRulesOk = useMemo(() => rules.every((r) => r.test(newPwd)), [newPwd]);
  const matches = newPwd.length > 0 && newPwd === confirm;
  const canSubmit = allRulesOk && matches && !submitting;

  // Missing / stale token → send user back to the login gate.
  if (!token) {
    return (
      <div className="min-h-screen bg-[#F3F4F6] p-6" data-testid="pwd-change-missing-token">
        <div className="mx-auto max-w-md rounded-2xl bg-white p-8 shadow-sm">
          <h1 className="font-serif text-2xl text-slate-900">Session expired</h1>
          <p className="mt-2 text-sm text-slate-600">
            Your password-change session is no longer valid. Please sign in again to restart.
          </p>
          <button
            type="button"
            data-testid="pwd-change-back-login"
            onClick={() => navigate("/admin/login", { replace: true })}
            className="mt-6 inline-flex h-11 items-center gap-2 rounded-full bg-[#0398FC] px-5 text-sm font-semibold text-black"
          >
            <ArrowLeft className="h-4 w-4" /> Back to sign in
          </button>
        </div>
      </div>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!matches) {
      setError("New password and confirmation do not match.");
      return;
    }
    if (!allRulesOk) {
      setError("Please meet every password requirement below.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/auth/change-password-first-login", {
        token,
        new_password: newPwd,
        confirm_password: confirm,
      });
      // Also drop any local session artefact (defence in depth).
      localStorage.removeItem("png_token");
      setDone(true);
    } catch (err) {
      const msg = formatError(err);
      setError(msg);
      // Expired / already-used tokens → send back to login shortly.
      const status = err?.response?.status;
      const lower = typeof msg === "string" ? msg.toLowerCase() : "";
      if (status === 400 && (lower.includes("expired") || lower.includes("already been used") || lower.includes("invalid password change token"))) {
        setTimeout(() => navigate("/admin/login", { replace: true }), 2500);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen bg-[#F3F4F6] p-6" data-testid="pwd-change-success-screen">
        <div className="mx-auto max-w-md rounded-2xl bg-white p-8 shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
            <ShieldCheck className="h-8 w-8 text-emerald-600" />
          </div>
          <h1 className="mt-5 text-center font-serif text-2xl text-slate-900">Password updated</h1>
          <p className="mt-2 text-center text-sm text-slate-600">
            Please sign in with your new password to continue.
          </p>
          <button
            type="button"
            data-testid="pwd-change-goto-login"
            onClick={() => navigate("/admin/login", { replace: true })}
            className="mt-6 h-12 w-full rounded-full bg-[#0398FC] text-sm font-semibold text-black"
          >
            Continue to sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F3F4F6] p-6" data-testid="pwd-change-screen">
      <div className="mx-auto max-w-md rounded-2xl bg-white p-8 shadow-sm">
        <div className="text-center">
          <Home className="mx-auto h-12 w-12 fill-[#0398FC] text-[#0398FC]" />
          <div className="mt-1 text-xs font-bold tracking-widest text-sky-700">TRELPNG</div>
          <h1 className="mt-4 font-serif text-2xl text-slate-900">Set a new password</h1>
          <p className="mt-2 text-sm text-slate-600">
            For your security, choose a new password before continuing to your workspace.
          </p>
          {email && (
            <p className="mt-2 text-xs text-slate-500" data-testid="pwd-change-email-hint">
              Signed in as <span className="font-semibold text-slate-700">{email}</span>
            </p>
          )}
        </div>

        <form onSubmit={submit} className="mt-6 space-y-4" data-testid="pwd-change-form">
          <PasswordField id="new-password" label="New password" value={newPwd} onChange={setNewPwd} autoFocus />
          <PasswordField id="confirm-password" label="Confirm new password" value={confirm} onChange={setConfirm} />

          <StrengthChecklist password={newPwd} />

          {confirm.length > 0 && !matches && (
            <p className="text-xs text-red-600" data-testid="pwd-change-mismatch">Passwords do not match.</p>
          )}

          {error && (
            <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" data-testid="pwd-change-error">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            data-testid="pwd-change-submit"
            className="h-12 w-full rounded-full bg-[#0398FC] text-sm font-semibold text-black disabled:opacity-60"
          >
            {submitting ? "Updating password…" : "Update password"}
          </button>

          <button
            type="button"
            onClick={() => navigate("/admin/login", { replace: true })}
            data-testid="pwd-change-cancel"
            className="mx-auto flex items-center gap-1.5 text-xs font-semibold text-slate-500"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Cancel and return to sign in
          </button>
        </form>
      </div>
    </div>
  );
}
