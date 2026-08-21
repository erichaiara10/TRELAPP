import React from "react";
import { Navigate, useLocation } from "react-router-dom";

// Compatibility fallback: any legacy /admin/login bookmark opens the approved
// common account popup on its Log In tab. The rejected standalone
// "TRELPNG sign in" page is no longer served.
export default function Login() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  params.set("auth", "login");
  if (!params.get("next")) params.set("next", "/admin");
  return <Navigate to={`/add-property?${params.toString()}`} replace />;
}
