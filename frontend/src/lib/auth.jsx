import React, { createContext, useContext, useEffect, useState } from "react";
import { api, formatError } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=loading, false=anon, obj=auth
  useEffect(() => {
    const t = localStorage.getItem("png_token");
    if (!t) { setUser(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => {
      localStorage.removeItem("png_token"); setUser(false);
    });
  }, []);

  const login = async (email, password) => {
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("png_token", data.token);
      setUser({ id: data.id, email: data.email, name: data.name, role: data.role });
      return { ok: true };
    } catch (e) { return { ok: false, error: formatError(e) }; }
  };

  const logout = async () => {
    localStorage.removeItem("png_token");
    setUser(false);
    try { await api.post("/auth/logout"); } catch {}
  };

  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
