import React from "react";
import { sanitizeName, NAME_MAX } from "@/lib/validators";

/**
 * Sanitised name input. A–Z, spaces, ', -. Max 25 chars. Shows a throttled
 * toast on rejected keystrokes.
 */
export default function NameInput({
  value = "",
  onChange,
  error,
  testId,
  placeholder = "e.g. Jane Doe",
  ...rest
}) {
  return (
    <div>
      <input
        {...rest}
        type="text"
        value={value}
        placeholder={placeholder}
        maxLength={NAME_MAX}
        onChange={(e) => {
          const clean = sanitizeName(e.target.value, { notify: true });
          onChange?.(clean);
        }}
        data-testid={testId}
        className={`w-full border rounded-lg px-3 py-2.5 bg-white ${error ? "border-destructive focus:ring-1 focus:ring-destructive" : "border-border"}`}
      />
      {error && (
        <p className="mt-1 text-[11px] text-destructive" data-testid={testId ? `${testId}-error` : undefined}>{error}</p>
      )}
    </div>
  );
}
