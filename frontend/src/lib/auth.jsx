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

  const login = useCallback(async (email, password) => {
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("png_token", data.token);
      setUser({ id: data.id, email: data.email, name: data.name, role: data.role });
      return { ok: true };
    } catch (e) { return { ok: false, error: formatError(e) }; }
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem("png_token");
    setUser(false);
    try { await api.post("/auth/logout"); }
    catch (e) {
      if (process.env.NODE_ENV !== "production") console.warn("Logout API failed (token already cleared locally):", e?.message);
    }
  }, []);

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
