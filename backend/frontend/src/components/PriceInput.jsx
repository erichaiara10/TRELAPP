import React from "react";
import { sanitizePrice, formatPGK, PRICE_MAX } from "@/lib/validators";

/**
 * Digits-only price input with a locked "K" prefix and a live formatted preview
 * (e.g. "K 850,000"). Enforces PRICE_MAX (K100M).
 */
export default function PriceInput({
  value = "",
  onChange,
  error,
  testId = "price",
  placeholder = "e.g. 850000",
  showPreview = true,
  ...rest
}) {
  const preview = formatPGK(value);
  return (
    <div>
      <div className={`flex items-stretch rounded-lg overflow-hidden border bg-white focus-within:ring-1 ${error ? "border-destructive focus-within:ring-destructive" : "border-border focus-within:ring-pine-500"}`}>
        <span className="px-3 py-2.5 bg-sand-50 text-xs font-mono text-muted-foreground border-r border-border" aria-label="PGK">K</span>
        <input
          {...rest}
          type="text"
          inputMode="numeric"
          value={value ?? ""}
          placeholder={placeholder}
          onChange={(e) => onChange?.(sanitizePrice(e.target.value, { notify: true }))}
          onKeyDown={(e) => {
            if (e.key.length === 1 && !/[0-9]/.test(e.key)) e.preventDefault();
          }}
          data-testid={`${testId}-input`}
          className="flex-1 px-3 py-2.5 text-sm bg-transparent outline-none min-w-0"
          aria-describedby={`${testId}-preview`}
          maxLength={String(PRICE_MAX).length}
        />
      </div>
      {showPreview && preview && (
        <div id={`${testId}-preview`} data-testid={`${testId}-preview`} className="mt-1 text-[11px] text-muted-foreground">
          {preview}
        </div>
      )}
      {error && (
        <p className="mt-1 text-[11px] text-destructive" data-testid={`${testId}-error`}>{error}</p>
      )}
    </div>
  );
}
