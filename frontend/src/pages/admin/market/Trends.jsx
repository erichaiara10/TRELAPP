// 4. Price Trends — market-level intelligence dashboard.
// Depends on aggregated snapshot data (Phase C+F). Phase 1 = placeholder
// preview describing every chart from the mockup.
import React from "react";
import { PageHeader, PhaseBanner, Section } from "./_shared";

const CHARTS = [
  ["Sale price trend (median)", "Line chart per location · last 12 months"],
  ["Rent trend (median monthly)", "Line chart per location · last 12 months"],
  ["Median asking price by suburb", "Top suburbs bar chart"],
  ["Price distribution by property class", "Donut chart"],
  ["Price trend heatmap", "% 12-month change by city × class"],
  ["Top rising / falling areas", "Twin tables"],
  ["Sample counts by city", "Sale / rent / total table"],
];

export default function MarketTrends() {
  return (
    <div data-testid="market-trends-page">
      <PageHeader
        title="Price Trends"
        subtitle="Aggregated median asking price and monthly rent movements across cities, suburbs and property classes — sourced from the deduplicated Master Property snapshots."
      />

      <PhaseBanner phase="Phase C — Guidance Engine + Phase F — Aggregation Dashboard" testid="trends-placeholder">
        Live trend charts activate once the guidance engine begins persisting weighted medians and confidence scores at the (suburb × class × purpose) grain.
      </PhaseBanner>

      <div className="grid md:grid-cols-2 gap-3 mt-4">
        {CHARTS.map(([title, hint]) => (
          <Section key={title} title={title} testid={`trend-preview-${title.replace(/\s+/g, "-").toLowerCase()}`}>
            <div className="text-xs text-muted-foreground">{hint}</div>
            <div className="mt-3 h-32 bg-muted/40 rounded" aria-hidden />
          </Section>
        ))}
      </div>

      <div className="mt-4 text-xs text-muted-foreground">
        All price data is aggregated from active listings and recent transactions. Figures will be indicative and subject to data quality and coverage.
      </div>
    </div>
  );
}
