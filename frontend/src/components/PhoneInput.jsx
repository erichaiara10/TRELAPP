import React, { useMemo } from "react";
import { COUNTRIES, parsePhone, joinPhone, sanitizeDigits } from "@/lib/validators";

/**
 * Phone input with a country-code dropdown (PNG +675 / Australia +61).
 * Enforces digit-only input and a country-specific length (PNG 8, AU 9).
 * The `value` prop and onChange callback use the concatenated form: "+67576281552".
 */
export default function PhoneInput({
  value = "",
  onChange,
  error,
  testId = "phone",
  placeholder,
  ...rest
}) {
  const { country, national } = useMemo(() => parsePhone(value), [value]);

  const setCountry = (dial) => {
    const c = COUNTRIES.find((x) => x.dial === dial) || COUNTRIES[0];
    onChange?.(joinPhone(c.dial, national));
  };
  const setDigits = (raw) => {
    const digits = sanitizeDigits(raw, { notify: true }).slice(0, country.digits);
    onChange?.(joinPhone(country.dial, digits));
  };

  return (
    <div>
      <div className={`flex items-stretch rounded-lg overflow-hidden border bg-white focus-within:ring-1 ${error ? "border-destructive focus-within:ring-destructive" : "border-border focus-within:ring-pine-500"}`}>
        <select
          value={country.dial}
          onChange={(e) => setCountry(e.target.value)}
          data-testid={`${testId}-country`}
          className="px-2 py-2.5 bg-sand-50 text-sm border-r border-border outline-none"
          aria-label="Country code"
        >
          {COUNTRIES.map((c) => (
            <option key={c.code} value={c.dial}>{c.label}</option>
          ))}
        </select>
        <input
          {...rest}
          type="tel"
          inputMode="numeric"
          value={national}
          placeholder={placeholder ?? `${country.digits} digits`}
          onChange={(e) => setDigits(e.target.value)}
          onKeyDown={(e) => {
            // Block obvious junk before it reaches the input value
            if (e.key.length === 1 && !/[0-9]/.test(e.key)) {
              e.preventDefault();
              // toast is fired via sanitizeDigits on paste; direct keystroke here silently blocked
            }
          }}
          data-testid={`${testId}-input`}
          className="flex-1 px-3 py-2.5 text-sm bg-transparent outline-none min-w-0"
        />
      </div>
      {error && (
        <p className="mt-1 text-[11px] text-destructive" data-testid={`${testId}-error`}>{error}</p>
      )}
    </div>
  );
}
