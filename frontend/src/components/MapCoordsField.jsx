import React, { useMemo, useState, lazy, Suspense } from "react";
import { MapPin, ExternalLink, AlertCircle, Map as MapIcon } from "lucide-react";

const MapPickerDialog = lazy(() => import("@/components/MapPickerDialog"));

export const MAPS_BASE = "https://www.google.com/maps?q=";
export const COORDS_HELP =
  "Open Google Maps, drop a pin on your property, right-click the pin, copy the coordinates, and paste them after the link above.";

/**
 * Extract "lat,lng" from any of the following inputs:
 *  • Raw coords: "-9.4438,147.1803", "-9.4438, 147.1803", "-9.4438 147.1803"
 *  • Full Google Maps URL with ?q= param
 *  • Google Maps place URLs like "/maps/@-9.4438,147.1803,17z"
 *  • Google Maps search URLs with numeric coord pairs anywhere
 * Returns null when nothing parseable is found.
 */
export function parseCoords(input) {
  if (!input) return null;
  const s = String(input).trim();
  if (!s) return null;
  // Match a lat,lng pair (allow whitespace, commas, or slashes between)
  // lat: -90..90, lng: -180..180 (loose regex, we validate below)
  const re = /(-?\d+(?:\.\d+)?)\s*[,\s/]\s*(-?\d+(?:\.\d+)?)/;
  const m = s.match(re);
  if (!m) return null;
  const lat = parseFloat(m[1]);
  const lng = parseFloat(m[2]);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return `${lat},${lng}`;
}

/**
 * Reusable Google Maps coordinate input.
 *  - Hard-coded read-only prefix `https://www.google.com/maps?q=`
 *  - Accepts raw coords OR a pasted Google Maps URL — auto-extracts lat,lng
 *  - Shows the instructions and a live "View on Google Maps" link that
 *    always opens a clean `https://www.google.com/maps?q=lat,lng` URL
 *
 * Value: whatever the user typed (raw string). Consumers should read the
 * raw value; the normalized coords are exposed via `parseCoords(value)` or
 * `mapsUrlFromCoords(value)` (which now normalizes internally).
 */
export default function MapCoordsField({
  label = "Google Maps location",
  value = "",
  onChange,
  testId = "map-coords",
  required = false,
  city = "",
  suburb = "",
  province = "",
}) {
  const raw = (value || "").trim();
  const coords = useMemo(() => parseCoords(raw), [raw]);
  const previewHref = coords ? `${MAPS_BASE}${coords}` : "";
  const invalid = raw.length > 0 && !coords;
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <div className="col-span-1 md:col-span-2" data-testid={testId}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
        <MapPin className="w-3 h-3 text-pine-500" />
        {label}
        {required && <span className="text-destructive ml-0.5" aria-label="required">*</span>}
      </div>
      <div className={`mt-1 flex items-stretch rounded-lg overflow-hidden border bg-white focus-within:ring-1 ${invalid ? "border-destructive focus-within:ring-destructive" : "border-border focus-within:ring-pine-500"}`}>
        <span
          className="px-3 py-2 bg-sand-50 text-xs font-mono text-muted-foreground border-r border-border select-all whitespace-nowrap"
          aria-label="Base link (auto-prefixed)"
          data-testid={`${testId}-prefix`}
        >
          {MAPS_BASE}
        </span>
        <input
          type="text"
          inputMode="text"
          placeholder="-9.4438,147.1803  (or paste a Google Maps URL)"
          value={value ?? ""}
          onChange={(e) => onChange?.(e.target.value)}
          className="flex-1 px-3 py-2 text-sm bg-transparent outline-none min-w-0"
          data-testid={`${testId}-input`}
          aria-describedby={`${testId}-help`}
        />
      </div>
      <p id={`${testId}-help`} className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground" data-testid={`${testId}-help`}>
        {COORDS_HELP}
      </p>
      {invalid && (
        <p className="mt-1 flex items-start gap-1 text-[11px] text-destructive" data-testid={`${testId}-invalid`}>
          <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
          <span>Couldn't detect coordinates. Please paste them as <code>lat,lng</code> (e.g. <code>-9.4438,147.1803</code>).</span>
        </p>
      )}
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-[#0d50e0] hover:bg-[#0b44c2] text-white text-xs font-medium"
          data-testid={`${testId}-pick-btn`}
        >
          <MapIcon className="w-3 h-3" /> Pick on Map
        </button>
        {previewHref && (
          <a
            href={previewHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-pine-500 hover:bg-pine-600 text-white text-xs font-medium"
            data-testid={`${testId}-preview`}
          >
            View on Google Maps <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
      {previewHref && (
        <div className="mt-1 text-[10px] text-muted-foreground font-mono break-all" data-testid={`${testId}-resolved`}>
          Opens: {previewHref}
        </div>
      )}
      {pickerOpen && (
        <Suspense fallback={null}>
          <MapPickerDialog
            open={pickerOpen}
            onOpenChange={setPickerOpen}
            initialCoords={value}
            city={city}
            suburb={suburb}
            province={province}
            onConfirm={(latlng) => onChange?.(latlng)}
          />
        </Suspense>
      )}
    </div>
  );
}

/**
 * Given whatever the user stored in map_coords (raw coords OR a full URL),
 * returns a clean `https://www.google.com/maps?q=lat,lng` URL — or null
 * when nothing parseable was found. Use in "View on Map" buttons.
 */
export function mapsUrlFromCoords(input) {
  const coords = parseCoords(input);
  return coords ? `${MAPS_BASE}${coords}` : null;
}
