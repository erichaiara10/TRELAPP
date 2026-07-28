import React from "react";

const BRAND_BLUE = "#0d50e0";

/**
 * Section card used to group public-form fields into visually distinct chunks.
 * Renders a numbered header with an icon tile matching the Sell-page blue theme.
 *
 * Usage:
 *   <FormSection num={1} icon={User} title="Owner Information" hint="Contact details">
 *     <div className="grid md:grid-cols-2 gap-4">…</div>
 *   </FormSection>
 */
export default function FormSection({ num, icon: Icon, title, hint, testId, children }) {
  return (
    <section
      className="rounded-2xl bg-white border border-border p-6 md:p-8"
      data-testid={testId}
    >
      <header className="flex items-start gap-3 mb-5">
        {Icon && (
          <div
            className="w-10 h-10 rounded-xl grid place-items-center shrink-0"
            style={{ backgroundColor: `${BRAND_BLUE}15`, color: BRAND_BLUE }}
            aria-hidden="true"
          >
            <Icon className="w-5 h-5" strokeWidth={1.75} />
          </div>
        )}
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">
            {num != null && <span>Step {num}</span>}
          </div>
          <h2 className="font-serif text-xl sm:text-2xl leading-tight text-ink-900 mt-0.5">
            {title}
          </h2>
          {hint && <p className="text-xs text-muted-foreground mt-1 italic">{hint}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}
