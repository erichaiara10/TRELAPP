import React from "react";
import { Navigate, useLocation } from "react-router-dom";

// Compatibility fallback: any legacy /register bookmark opens the approved
// common account popup on its Create Account tab.
export default function Register() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  params.set("auth", "register");
  if (!params.get("next")) params.set("next", "/advertiser");
  return <Navigate to={`/add-property?${params.toString()}`} replace />;
}
