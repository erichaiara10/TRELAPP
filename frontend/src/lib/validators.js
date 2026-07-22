/**
 * Shared client-side data validators / sanitisers.
 *
 * Rules (as agreed with the product owner):
 *  - NAMES: A–Z, a–z, spaces, apostrophes ('), hyphens (-). Max 25 chars.
 *  - PHONES: country code dropdown (PNG +675 / AU +61) + digits only.
 *      PNG requires exactly 8 digits after prefix. AU requires 9 digits.
 *  - MONEY: digits only, 0 ≤ value ≤ 100,000,000 (K100M).
 *  - Price logic: max ≥ min.
 *  - Rejected keystrokes fire a THROTTLED toast (max one per 2 s).
 */
import { toast } from "sonner";

// ---- Throttled toast helper -------------------------------------------------
const _lastToastAt = { current: 0 };
export function warnOnce(message) {
  const now = Date.now();
  if (now - _lastToastAt.current < 2000) return;
  _lastToastAt.current = now;
  toast.warning(message);
}

// ---- Sanitisers -------------------------------------------------------------
export const NAME_MAX = 25;
export function sanitizeName(raw, opts = {}) {
  const src = String(raw ?? "");
  let cleaned = src.replace(/[^A-Za-z\s'-]/g, "");
  cleaned = cleaned.replace(/\s{2,}/g, " ");
  const truncated = cleaned.slice(0, NAME_MAX);
  if (opts.notify) {
    if (cleaned.length !== src.length) warnOnce("Names can only contain letters, spaces, apostrophes and hyphens.");
    else if (truncated.length !== cleaned.length) warnOnce(`Names are limited to ${NAME_MAX} characters.`);
  }
  return truncated;
}

export function sanitizeDigits(raw, opts = {}) {
  const src = String(raw ?? "");
  const cleaned = src.replace(/\D/g, "");
  if (opts.notify && cleaned.length !== src.length) warnOnce("Only digits (0–9) are allowed here.");
  return cleaned;
}

// ---- Phone ------------------------------------------------------------------
export const COUNTRIES = [
  { code: "PG", dial: "+675", label: "PNG (+675)", digits: 8 },
  { code: "AU", dial: "+61",  label: "Australia (+61)", digits: 9 },
];
export const DEFAULT_COUNTRY = COUNTRIES[0];

export function parsePhone(full) {
  const s = String(full || "").trim();
  for (const c of COUNTRIES) {
    if (s.startsWith(c.dial)) return { country: c, national: sanitizeDigits(s.slice(c.dial.length)) };
  }
  return { country: DEFAULT_COUNTRY, national: sanitizeDigits(s) };
}
export function joinPhone(countryDial, national) {
  const digits = sanitizeDigits(national);
  return digits ? `${countryDial}${digits}` : "";
}
export function isValidPhone(fullOrParts) {
  const { country, national } =
    typeof fullOrParts === "string" ? parsePhone(fullOrParts) : fullOrParts;
  return national.length === country.digits;
}

// ---- Money / Price ----------------------------------------------------------
export const PRICE_MIN = 0;
export const PRICE_MAX = 100_000_000; // K100 million

export function sanitizePrice(raw, opts = {}) {
  const cleaned = sanitizeDigits(raw, opts);
  if (cleaned === "") return "";
  const n = Math.min(Number(cleaned), PRICE_MAX);
  if (opts.notify && Number(cleaned) > PRICE_MAX) warnOnce(`Prices cannot exceed K ${PRICE_MAX.toLocaleString()}.`);
  return String(n);
}
export const formatPGK = (n) => {
  const v = Number(n);
  if (!Number.isFinite(v) || v <= 0) return "";
  return `K ${v.toLocaleString()}`;
};

// ---- Email ------------------------------------------------------------------
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const isValidEmail = (v) => EMAIL_RE.test(String(v || "").trim());

// ---- Location ---------------------------------------------------------------
export const isPlaceholder = (v) =>
  !v || v === "" || v === "—" || String(v).toLowerCase().startsWith("select");

// ---- Form-level helpers -----------------------------------------------------
/**
 * Validate a plain object of values against a list of required keys and
 * optional min/max price fields. Returns { errors, firstErrorKey } where
 * errors is a dict of key -> message.
 */
export function validateForm(values, requiredKeys = [], opts = {}) {
  const errors = {};
  requiredKeys.forEach((k) => {
    const v = values[k];
    if (v === undefined || v === null || String(v).trim() === "" || isPlaceholder(v)) {
      errors[k] = "This field is required";
    }
  });
  if (values.email !== undefined && values.email !== "" && !isValidEmail(values.email)) {
    errors.email = "Please enter a valid email";
  }
  if (opts.phoneKey && values[opts.phoneKey]) {
    if (!isValidPhone(values[opts.phoneKey])) {
      const c = parsePhone(values[opts.phoneKey]).country;
      errors[opts.phoneKey] = `Please enter a valid ${c.label} number (${c.digits} digits)`;
    }
  }
  if (opts.minKey && opts.maxKey) {
    const min = Number(values[opts.minKey]) || 0;
    const max = Number(values[opts.maxKey]) || 0;
    if (min > 0 && max > 0 && max < min) {
      errors[opts.maxKey] = "Max price must be greater than or equal to min price";
    }
  }
  const firstErrorKey = Object.keys(errors)[0] || null;
  return { errors, firstErrorKey, ok: firstErrorKey === null };
}
