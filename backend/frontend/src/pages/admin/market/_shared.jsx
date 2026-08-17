// Shared building blocks for the Property Data Aggregation admin screens.
// Kept tiny and dumb so each screen can compose its own layout while sharing
// the same visual grammar (headings, KPI cards, empty-state banners).
import React from "react";

export function PageHeader({ title, subtitle, actions, testid }) {
  return (
    <div className="flex items-start justify-between gap-6 mb-5" data-testid={testid || "market-page-header"}>
      <div>
        <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">Property Data Aggregation</div>
        <h1 className="text-2xl font-semibold mt-1">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function KpiCard({ label, value, hint, testid }) {
  return (
    <div className="bg-white rounded-lg border border-border p-4" data-testid={testid}>
      <div className="text-[11px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold mt-1 tabular-nums">{value ?? "—"}</div>
      {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

// Empty-state banner used by screens whose data engine lands in a later phase
// (Comparables/Trends/Price Compare land in Phase C, evidence populates once
// scrapers land in Phase E). Keeps the menu functional without pretending
// features exist that don't.
export function PhaseBanner({ phase, children, testid }) {
  return (
    <div className="bg-white rounded-lg border border-dashed border-border p-6" data-testid={testid || "market-phase-banner"}>
      <div className="inline-flex items-center gap-2 text-[10px] uppercase tracking-widest text-white bg-[#2A5B46] px-2 py-1 rounded">
        {phase}
      </div>
      <div className="mt-3 text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

export function Section({ title, actions, children, testid }) {
  return (
    <div className="bg-white rounded-lg border border-border" data-testid={testid}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="text-sm font-medium">{title}</div>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}
