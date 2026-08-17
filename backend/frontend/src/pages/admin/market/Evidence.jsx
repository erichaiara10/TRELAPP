// 2. Market Evidence — reads from /api/admin/market/listings.
// Main table columns are unchanged (Record ID, Source, Purpose, Class,
// Location, Price, Last Seen, Status). Clicking anywhere on a row opens
// a right-hand slide-out record inspector that surfaces every field NOT
// already visible in the row (source URL, subtype, allotment/section/
// portion, beds/baths, land/building area, full address, match info,
// raw scraper payload, timestamps).
import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader, KpiCard, Section, PhaseBanner } from "./_shared";

const formatMoney = (value) => {
  if (value === null || value === undefined || value === "") return "—";
  const amount = Number(value);
  return Number.isFinite(amount) ? `K${amount.toLocaleString("en-US", { maximumFractionDigits: 2 })}` : "—";
};

const formatPngDateTime = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Pacific/Port_Moresby", day: "2-digit", month: "short", year: "numeric",
    hour: "numeric", minute: "2-digit", second: "2-digit", hour12: true,
  }).format(date).replace(/^0/, "").replace(" at ", ", ").replace(/\b(am|pm)\b/i, (v) => v.toUpperCase());
};

const rentPeriodLabel = (period) => {
  const labels = { monthly: "month", weekly: "week", fortnightly: "fortnight", daily: "day", annual: "year" };
  return period && labels[period] ? ` per ${labels[period]}` : "";
};

export default function MarketEvidence() {
  const [listings, setListings] = useState([]);
  const [summary, setSummary] = useState({});
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    api.get("/admin/market/listings?limit=100").then((r) => setListings(r.data || [])).catch(() => {});
    api.get("/admin/market/summary").then((r) => setSummary(r.data)).catch(() => {});
  }, []);

  // ESC closes the inspector — small quality-of-life win for ops who
  // spend all day paging through listings.
  useEffect(() => {
    if (!selected) return;
    const onKey = (e) => { if (e.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  return (
    <div data-testid="market-evidence-page">
      <PageHeader
        title="Market Evidence"
        subtitle="Every raw external listing observed by TREL's collectors, deduplicated by source ad ID and linked to the master property identity graph."
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <KpiCard label="Active Evidence" value={summary.active_listings} testid="kpi-evidence-active" />
        <KpiCard label="Total Listings" value={summary.market_listings} testid="kpi-evidence-total" />
        <KpiCard label="Linked to Masters" value={summary.matches_active} testid="kpi-evidence-linked" />
        <KpiCard label="Master Properties" value={summary.master_properties} testid="kpi-evidence-masters" />
        <KpiCard label="Data Sources" value={`${summary.active_sources ?? 0}/${summary.sources ?? 0}`} testid="kpi-evidence-sources" />
      </div>

      <Section title="Active Evidence" testid="market-evidence-table">
        {listings.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">
            No market listings yet. Once a public listing collector is configured (Phase E) and its first run completes,
            deduplicated records will appear here for identity matching.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                  <th className="py-2 pr-3">Record ID</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Purpose</th>
                  <th className="py-2 pr-3">Class</th>
                  <th className="py-2 pr-3">Location</th>
                  <th className="py-2 pr-3">Price</th>
                  <th className="py-2 pr-3">Last Seen</th>
                  <th className="py-2 pr-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {listings.map((l) => (
                  <tr key={l.id}
                      onClick={() => setSelected(l)}
                      className={`border-b border-border/60 cursor-pointer hover:bg-[#F1F6F3] transition-colors ${selected?.id === l.id ? "bg-[#F1F6F3]" : ""}`}
                      data-testid={`evidence-row-${l.id}`}>
                    <td className="py-2 pr-3 font-mono text-xs">{l.id.slice(0, 8)}</td>
                    <td className="py-2 pr-3">{l.source_id?.slice(0, 8)}</td>
                    <td className="py-2 pr-3">{l.purpose}</td>
                    <td className="py-2 pr-3">{l.property_class || "—"}</td>
                    <td className="py-2 pr-3">{[l.suburb, l.city].filter(Boolean).join(", ")}</td>
                    <td className="py-2 pr-3 tabular-nums">{formatMoney(l.price)}</td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{formatPngDateTime(l.last_seen)}</td>
                    <td className="py-2 pr-3 uppercase text-xs tracking-widest">{l.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-[11px] text-muted-foreground mt-3">
              Click any row to open the full record inspector.
            </div>
          </div>
        )}
      </Section>

      <div className="mt-4">
        <PhaseBanner phase="Phase E">
          Filter chips per the mockup ship with the first collector rollout. Full record inspector is live — click any row.
        </PhaseBanner>
      </div>

      {selected && <RecordInspector record={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}


// ---------------- Record Inspector ----------------
// Right-hand slide-out surfacing every field not already visible in the
// main table row. Grouped so ops can scan quickly:
//   Identifiers · Classification · Parcel · Size / Rooms · Location detail
//   · Match info · Timestamps / ops · Raw payload
// Empty values render as an em-dash so gaps in scraper coverage are
// obvious at a glance.
function RecordInspector({ record, onClose }) {
  const url = record.source_url;
  const moneyLabel = record.purpose === "rent" ? "Rent" : "Asking Price";
  const moneyValue = `${formatMoney(record.price)}${record.purpose === "rent" ? rentPeriodLabel(record.rent_period) : ""}`;
  const groups = [
    {
      title: "Listing",
      rows: [
        ["Purpose", record.purpose],
        [moneyLabel, <strong className="text-lg tabular-nums text-[#2A5B46]">{moneyValue}</strong>],
        ["Property Class", record.property_class],
        ["Property Subtype", record.property_subtype],
        ["Record ID (full)", <span className="font-mono text-xs break-all">{record.id}</span>],
      ],
    },
    {
      title: "Property Identification",
      rows: [
        ["Lot / Allotment", record.allotment_number],
        ["Section", record.section_number],
        ["Portion", record.portion_number],
      ],
    },
    {
      title: "Location",
      rows: [
        ["Property / Building Name", record.building_name],
        ["Street", record.street], ["Suburb", record.suburb],
        ["Local Area", record.local_area], ["City", record.city],
        ["Province", record.province],
      ],
    },
    {
      title: "Property Details",
      rows: [
        ["Bedrooms", record.bedrooms], ["Bathrooms", record.bathrooms],
        ["Land Area", record.land_area_m2 ? `${record.land_area_m2} m²` : null],
        ["Building / Floor Area", record.building_area_m2 ? `${record.building_area_m2} m²` : null],
      ],
    },
    {
      title: "Source",
      rows: [
        ["Source", <span className="font-mono text-xs break-all">{record.source_id}</span>],
        ["Source Listing ID", record.source_listing_id],
        ["Listing URL", url ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-[#2A5B46] underline break-all text-xs" data-testid="inspector-source-url">{url}</a> : "—"],
      ],
    },
    {
      title: "Record History",
      rows: [
        ["First Seen", formatPngDateTime(record.first_seen)],
        ["Last Seen", formatPngDateTime(record.last_seen)],
        ["Created", formatPngDateTime(record.created_at)],
        ["Updated", formatPngDateTime(record.updated_at)],
        ["Exclusion Reason", record.exclusion_reason],
        ["Alias Map Version", record.alias_map_version],
      ],
    },
  ];

  return (
    <>
      {/* Backdrop — purely decorative dim behind the panel. It has
          pointer-events:none so clicks on table rows underneath pass
          straight through and switch the inspected record. Close is via
          the X button in the panel or the Escape key. */}
      <div className="fixed inset-y-0 left-0 z-40 bg-black/20 pointer-events-none"
           style={{ right: "720px" }}
           data-testid="record-inspector-backdrop" />

      <div className="fixed right-0 top-0 h-full w-full max-w-[720px] bg-white shadow-2xl overflow-y-auto z-50"
           data-testid="record-inspector">
        <div className="sticky top-0 bg-white border-b border-border p-5 flex items-start justify-between z-10">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Market Listing</div>
            <div className="text-xl font-semibold mt-1" data-testid="inspector-title">
              {record.property_subtype || record.property_class || "Listing"}
              {record.suburb ? ` · ${record.suburb}` : ""}
            </div>
            <div className="text-xs text-muted-foreground mt-1 font-mono">
              {record.id}
            </div>
            <div className="text-[10px] text-muted-foreground mt-2">
              Click any other row to switch record · Esc / ✕ to close
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"
                  data-testid="inspector-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {groups.map((g) => (
            <FieldGroup key={g.title} title={g.title} rows={g.rows} />
          ))}

          {/* Raw payload — collapsed by default */}
          <details className="border border-border rounded" data-testid="inspector-raw-toggle">
            <summary className="cursor-pointer text-sm font-medium px-3 py-2 bg-[#FAFBFA] hover:bg-muted/40">
              Raw scraper payload
            </summary>
            <pre className="text-[11px] font-mono p-3 whitespace-pre-wrap break-words max-h-80 overflow-y-auto bg-white"
                 data-testid="inspector-raw-body">
              {JSON.stringify(record.raw_fields || {}, null, 2) || "{}"}
            </pre>
          </details>

          {/* Normalized payload (if the collector supplied one) */}
          {record.normalized_fields && Object.keys(record.normalized_fields).length > 0 && (
            <details className="border border-border rounded" data-testid="inspector-normalized-toggle">
              <summary className="cursor-pointer text-sm font-medium px-3 py-2 bg-[#FAFBFA] hover:bg-muted/40">
                Normalized fields
              </summary>
              <pre className="text-[11px] font-mono p-3 whitespace-pre-wrap break-words max-h-80 overflow-y-auto bg-white">
                {JSON.stringify(record.normalized_fields, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </>
  );
}


function FieldGroup({ title, rows }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2"
           data-testid={`inspector-group-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`}>
        {title}
      </div>
      <div className="border border-border rounded overflow-hidden">
        <table className="w-full text-sm">
          <tbody>
            {rows.map(([label, value], i) => (
              <tr key={label} className={i > 0 ? "border-t border-border/60" : ""}
                  data-testid={`inspector-field-${label.replace(/²/g, "2").replace(/³/g, "3").replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase()}`}>
                <td className="py-2 px-3 text-xs text-muted-foreground w-1/3 bg-[#FAFBFA] align-top">
                  {label}
                </td>
                <td className="py-2 px-3 align-top">
                  {value === null || value === undefined || value === "" ? (
                    <span className="text-muted-foreground">—</span>
                  ) : value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
