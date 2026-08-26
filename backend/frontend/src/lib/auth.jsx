import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import { api, formatError } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=loading, false=anon, obj=auth

  useEffect(() => {
    const t = localStorage.getItem("png_token");
    if (!t) { setUser(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => { localStorage.removeItem("png_token"); setUser(false); });
  }, []);

  const acceptSession = useCallback((data) => {
    localStorage.setItem("png_token", data.token);
    const authenticatedUser = { id: data.id, email: data.email, name: data.name, role: data.role, account_category: data.account_category, workspace_path: data.workspace_path, email_verified: data.email_verified !== false, profile_complete: data.profile_complete !== false };
    setUser(authenticatedUser);
    return { ok: true, user: authenticatedUser, workspacePath: data.workspace_path };
  }, []);

  const login = useCallback(async (email, password, turnstile_token) => {
    try {
      const { data } = await api.post("/auth/login", { email, password, turnstile_token });
      return acceptSession(data);
    } catch (e) { return { ok: false, error: formatError(e) }; }
  }, [acceptSession]);

  const googleLogin = useCallback(async (payload) => {
    try {
      const { data } = await api.post("/auth/google", payload);
      return acceptSession(data);
    } catch (e) { return { ok: false, error: formatError(e) }; }
  }, [acceptSession]);

  const register = useCallback(async (payload) => {
    try {
      const { data } = await api.post("/auth/register", payload);
      return acceptSession(data);
    } catch (e) { return { ok: false, error: formatError(e) }; }
  }, [acceptSession]);

  const verifyEmailToken = useCallback(async (token) => {
    try {
      const { data } = await api.post("/auth/verify-email-token", { token });
      return acceptSession(data);
    } catch (e) { return { ok: false, error: formatError(e) }; }
  }, [acceptSession]);

  const verifyEmailCode = useCallback(async (code) => {
    try {
      const { data } = await api.post("/auth/verify-email-code", { code });
      return acceptSession(data);
    } catch (e) { return { ok: false, error: formatError(e) }; }
  }, [acceptSession]);

  const logout = useCallback(async () => {
    localStorage.removeItem("png_token");
    setUser(false);
    try { await api.post("/auth/logout"); }
    catch (e) {
      if (process.env.NODE_ENV !== "production") console.warn("Logout API failed (token already cleared locally):", e?.message);
    }
  }, []);

  const updateUser = useCallback((updates) => {
    setUser((current) => current && ({ ...current, ...updates }));
  }, []);

  const value = useMemo(() => ({ user, login, googleLogin, register, verifyEmailToken, verifyEmailCode, logout, updateUser }), [user, login, googleLogin, register, verifyEmailToken, verifyEmailCode, logout, updateUser]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
