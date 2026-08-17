import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Use Authorization header (localStorage token) — avoids cross-origin cookie issues with wildcard CORS
export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("png_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function formatError(err) {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(", ");
  return String(d);
}

export const money = (v, ccy = "PGK") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: ccy, maximumFractionDigits: 0 }).format(v || 0);
