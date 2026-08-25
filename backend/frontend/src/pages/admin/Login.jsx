import React from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import AccountAccessDialog from "@/components/public/AccountAccessDialog";
import { useAuth } from "@/lib/auth";
import { destinationForUser } from "@/lib/accountRouting";

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const params = new URLSearchParams(location.search);
  const requestedPath = params.get("next") || "";

  if (user === null) return <div className="min-h-screen bg-slate-950 p-10 text-sm text-slate-300">Loading…</div>;
  if (user) return <Navigate to={destinationForUser(user, requestedPath)} replace />;

  return <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950" data-testid="generic-login-page">
    <AccountAccessDialog
      open
      initialTab="login"
      onClose={() => navigate("/", { replace: true })}
      next={requestedPath}
    />
  </main>;
}
