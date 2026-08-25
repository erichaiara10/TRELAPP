import React from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import AccountAccessDialog from "@/components/public/AccountAccessDialog";
import { useAuth } from "@/lib/auth";

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const params = new URLSearchParams(location.search);
  const requestedNext = params.get("next") || "/admin";
  const next = requestedNext === "/admin" || requestedNext.startsWith("/admin/") || requestedNext.startsWith("/admin?") ? requestedNext : "/admin";

  if (user === null) return <div className="min-h-screen bg-slate-950 p-10 text-sm text-slate-300">Loading…</div>;
  if (user) return <Navigate to={user.account_category === "STAFF" ? next : (user.workspace_path || "/")} replace />;

  return <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950" data-testid="staff-login-page">
    <AccountAccessDialog
      open
      initialTab="login"
      onClose={() => navigate("/", { replace: true })}
      next={next}
      loginOnly
      contextLabel="Secure Account Login"
    />
  </main>;
}
