// 7. Price Compare Results — final Seller / Buyer / Landlord / Renter outputs
// from the guidance engine. Powered by /api/admin/market/guidance-results
// once Phase C is wired.
import React from "react";
import { PageHeader, PhaseBanner, Section } from "./_shared";

const WORKFLOWS = [
  ["Seller Guidance", "Comparable count, observed range, weighted median, TREL indicative range, suggested listing range, confidence."],
  ["Buyer Price Check", "Position vs range (BELOW / WITHIN / ABOVE), % vs weighted median, comparable breakdown."],
  ["Landlord Rental Guidance", "Monthly comparable range, median monthly rent, TREL indicative monthly range, confidence."],
  ["Renter/Tenant Rent Check", "Position vs range, % vs weighted median monthly rent."],
];

export default function PriceCompareResults() {
  return (
    <div data-testid="market-price-compare-page">
      <PageHeader
        title="Price Compare Results"
        subtitle="Every guidance run produced by the engine — seller, buyer, landlord, renter — with the exact comparables, weights and configuration version used at calculation time."
      />

      <PhaseBanner phase="Phase C — Guidance Engine" testid="pcr-placeholder">
        Live results table with per-run inspector (subject property card, comparable list, weighted stats) lands with GUIDE-1.0.
      </PhaseBanner>

      <div className="grid md:grid-cols-2 gap-3 mt-4">
        {WORKFLOWS.map(([title, hint]) => (
          <Section key={title} title={title} testid={`pcr-preview-${title.replace(/\s+/g, "-").toLowerCase()}`}>
            <div className="text-sm text-muted-foreground">{hint}</div>
          </Section>
        ))}
      </div>
    </div>
  );
}
