// 7. Price Compare Results — final Seller / Buyer / Landlord / Renter outputs
// from the guidance engine. Powered by /api/admin/market/guidance-results
// once Phase C is wired.
import React, { useEffect, useState } from "react";
import { api, money } from "@/lib/api";
import { PageHeader, LoadError, Section } from "./_shared";

const WORKFLOWS = [
  ["Seller Guidance", "Comparable count, observed range, weighted median, TREL indicative range, suggested listing range, confidence."],
  ["Buyer Price Check", "Position vs range (BELOW / WITHIN / ABOVE), % vs weighted median, comparable breakdown."],
  ["Landlord Rental Guidance", "Monthly comparable range, median monthly rent, TREL indicative monthly range, confidence."],
  ["Renter/Tenant Rent Check", "Position vs range, % vs weighted median monthly rent."],
];

export default function PriceCompareResults() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const load = () => api.get("/admin/market/guidance/results?limit=100")
    .then((r) => { setRows(r.data || []); setError(""); })
    .catch((e) => setError(e?.response?.data?.detail || e?.message || "Results could not be loaded."));
  useEffect(load, []);
  return (
    <div data-testid="market-price-compare-page">
      <PageHeader
        title="Price Compare Results"
        subtitle="Every guidance run produced by the engine — seller, buyer, landlord, renter — with the exact comparables, weights and configuration version used at calculation time."
      />

      <LoadError message={error} onRetry={load} />
      <Section title={`Guidance runs (${rows.length})`} testid="price-results-table">
        {rows.length === 0 ? <div className="py-6 text-sm text-muted-foreground">No guidance results have been created yet.</div> :
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase border-b">
            <th className="py-2">Created</th><th>Workflow</th><th>Property</th><th>Range</th><th>Confidence</th><th>Comparables</th>
          </tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-b">
            <td className="py-2">{(row.created_at || "").slice(0, 19).replace("T", " ")}</td>
            <td>{row.outputs?.workflow || "—"}</td><td>{row.subject?.property_type || row.property_type || "—"}</td>
            <td>{row.range?.low != null && row.range?.high != null ? `${money(row.range.low)} – ${money(row.range.high)}` : "—"}</td>
            <td>{row.confidence || row.strength || "—"}</td><td>{row.comparable_count ?? row.comparables?.length ?? 0}</td>
          </tr>)}</tbody></table></div>}
      </Section>

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
