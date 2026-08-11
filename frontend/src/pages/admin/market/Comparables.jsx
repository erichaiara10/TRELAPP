// 3. Comparable Properties — subject + ranked comparables view.
// Powered by the Phase C guidance engine. For Phase 1 we render a
// descriptive placeholder that mirrors the mockup so admins can preview
// the eventual layout.
import React from "react";
import { PageHeader, PhaseBanner, Section } from "./_shared";

export default function MarketComparables() {
  return (
    <div data-testid="market-comparables-page">
      <PageHeader
        title="Comparable Properties"
        subtitle="Ranked comparables for a subject property with Comparable Quality Score, recency weighting, TREL Indicative Range and exclusion audit trail."
      />

      <PhaseBanner phase="Phase C — Guidance Engine" testid="comparables-placeholder">
        Live comparable-selection view lands with GUIDE-1.0. It will render three tabs (Direct Comparables, Supporting Evidence, Excluded/Outliers) plus the "Why this comparable was included" evidence breakdown for every row.
      </PhaseBanner>

      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <Section title="Subject Property (preview)" testid="comparables-subject-preview">
          <div className="text-sm text-muted-foreground">
            Address, purpose, class, subtype, bedrooms/bathrooms, land area and proposed price of the property under valuation.
            Fed by <span className="font-mono text-xs">/api/admin/market/valuation-requests</span> (Phase C).
          </div>
        </Section>
        <Section title="Comparable Summary (preview)" testid="comparables-summary-preview">
          <ul className="text-sm text-muted-foreground list-disc pl-5 space-y-1">
            <li>Weighted median</li>
            <li>Observed asking range (min–max after filters)</li>
            <li>TREL Indicative Range (weighted P25–P75)</li>
            <li>Unique comparables included (post dedupe + outlier)</li>
            <li>Market Guidance Confidence label (Strong / Moderate / Limited / Insufficient)</li>
          </ul>
        </Section>
      </div>
    </div>
  );
}
