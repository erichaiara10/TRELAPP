import React from "react";
import { MapPin, ExternalLink } from "lucide-react";

export const MAPS_BASE = "https://www.google.com/maps?q=";
export const COORDS_HELP =
  "Open Google Maps, drop a pin on your property, right-click the pin, copy the coordinates, and paste them after the link above.";

/**
 * Reusable Google Maps coordinate input.
 * - Displays the hard-coded base link `https://www.google.com/maps?q=` as a read-only prefix.
 * - Accepts just the coordinates (e.g. `-9.4438,147.1803`) — the full URL is composed on view.
 * - Shows the standard instructions and a live "Preview on Google Maps" link when coords are entered.
 *
 * Props:
 *  - label (default "Google Maps location")
 *  - value (coordinates string), onChange(str)
 *  - testId
 *  - required (bool, adds red asterisk)
 */
export default function MapCoordsField({
  label = "Google Maps location",
  value = "",
  onChange,
  testId = "map-coords",
  required = false,
}) {
  const clean = (value || "").trim();
  const previewHref = clean ? `${MAPS_BASE}${encodeURIComponent(clean)}` : "";

  return (
    <div className="col-span-1 md:col-span-2" data-testid={testId}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-1">
        <MapPin className="w-3 h-3 text-pine-500" />
        {label}
        {required && <span className="text-destructive ml-0.5" aria-label="required">*</span>}
      </div>
      <div className="mt-1 flex items-stretch rounded-lg overflow-hidden border border-border bg-white focus-within:ring-1 focus-within:ring-pine-500">
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
          placeholder="-9.4438,147.1803"
          value={clean}
          onChange={(e) => onChange?.(e.target.value)}
          className="flex-1 px-3 py-2 text-sm bg-transparent outline-none min-w-0"
          data-testid={`${testId}-input`}
          aria-describedby={`${testId}-help`}
        />
      </div>
      <p id={`${testId}-help`} className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground" data-testid={`${testId}-help`}>
        {COORDS_HELP}
      </p>
      {previewHref && (
        <a
          href={previewHref}
          target="_blank"
          rel="noreferrer"
          className="mt-1 inline-flex items-center gap-1 text-xs text-pine-500 hover:text-pine-600"
          data-testid={`${testId}-preview`}
        >
          Preview on Google Maps <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </div>
  );
}

/**
 * Given a coords string, returns the full https://www.google.com/maps?q=<coords> URL,
 * or null when coords is blank. Use in "View on Map" buttons.
 */
export function mapsUrlFromCoords(coords) {
  const c = (coords || "").trim();
  return c ? `${MAPS_BASE}${encodeURIComponent(c)}` : null;
}

/**
 * Same but for iframe embed (adds &output=embed).
 */
export function mapsEmbedFromCoords(coords) {
  const c = (coords || "").trim();
  return c ? `${MAPS_BASE}${encodeURIComponent(c)}&output=embed` : null;
}
