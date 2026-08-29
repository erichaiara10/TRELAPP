import React from "react";
import { NAME_MAX, isValidName } from "@/lib/validators";

/** Keep invalid text visible, explain it inline, and let form constraints block submission. */
export default function NameInput({
  value = "",
  onChange,
  error,
  testId,
  placeholder = "e.g. Jane Doe",
  ...rest
}) {
  const inlineError = error || (value && !isValidName(value)
    ? `Use letters, spaces, apostrophes or hyphens only (maximum ${NAME_MAX} characters).`
    : "");
  return (
    <div>
      <input
        {...rest}
        required
        type="text"
        value={value}
        placeholder={placeholder}
        maxLength={NAME_MAX}
        pattern="[A-Za-z\\s\'-]+"
        title="Use letters, spaces, apostrophes or hyphens only."
        aria-invalid={inlineError ? true : undefined}
        onChange={(e) => onChange?.(e.target.value)}
        data-testid={testId}
        className={`w-full border rounded-lg px-3 py-2.5 bg-white ${inlineError ? "border-destructive focus:ring-1 focus:ring-destructive" : "border-border"}`}
      />
      {inlineError && (
        <p className="mt-1 text-[11px] text-destructive" data-testid={testId ? `${testId}-error` : undefined}>{inlineError}</p>
      )}
    </div>
  );
}
