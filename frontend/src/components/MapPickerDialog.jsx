import React, { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Search, X, MapPin } from "lucide-react";
import { toast } from "sonner";
import { parseCoords } from "@/components/MapCoordsField";

// Fix well-known Leaflet default marker path issue in bundlers (webpack/CRA).
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const PORT_MORESBY = { lat: -9.4438, lng: 147.1803, zoom: 14 };

function ClickToPlace({ onPick }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

function Recenter({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    // Ensure tiles paint correctly when the map appears inside a dialog
    setTimeout(() => map.invalidateSize(), 50);
  }, [map]);
  useEffect(() => {
    if (center) map.setView([center.lat, center.lng], zoom ?? map.getZoom(), { animate: true });
  }, [center, zoom, map]);
  return null;
}

async function geocodeNominatim(query, timeoutMs = 5000) {
  if (!query) return null;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
    const res = await fetch(url, {
      headers: { Accept: "application/json", "Accept-Language": "en" },
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    const arr = await res.json();
    if (!Array.isArray(arr) || arr.length === 0) return null;
    const { lat, lon } = arr[0];
    const nlat = parseFloat(lat);
    const nlng = parseFloat(lon);
    if (Number.isNaN(nlat) || Number.isNaN(nlng)) return null;
    return { lat: nlat, lng: nlng };
  } catch {
    return null;
  } finally {
    clearTimeout(t);
  }
}

/**
 * Interactive OpenStreetMap picker.
 * Auto-centers on (in priority order):
 *   1. `initialCoords` (existing value)
 *   2. `suburb, city, province, Papua New Guinea`
 *   3. `city, province, Papua New Guinea`
 *   4. `province, Papua New Guinea`
 *   5. Port Moresby fallback
 */
export default function MapPickerDialog({
  open,
  onOpenChange,
  initialCoords = "",
  city = "",
  suburb = "",
  province = "",
  onConfirm,
}) {
  const [center, setCenter] = useState(null);
  const [zoom, setZoom] = useState(PORT_MORESBY.zoom);
  const [pin, setPin] = useState(null);
  const [contextLabel, setContextLabel] = useState("");
  const [locating, setLocating] = useState(false);
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  const initedFor = useRef(null);

  const parsedInitial = useMemo(() => {
    const s = parseCoords(initialCoords);
    if (!s) return null;
    const [lat, lng] = s.split(",").map(Number);
    return { lat, lng };
  }, [initialCoords]);

  // Auto-center chain (only runs when dialog opens with new session id).
  // We ALWAYS set an initial center synchronously so the map renders straight
  // away — geocoding then runs in the background and silently upgrades the
  // view if it succeeds. This prevents a stuck "Locating…" state when
  // Nominatim is blocked, slow, or rate-limited.
  useEffect(() => {
    if (!open) return;
    const sessionKey = `${initialCoords}|${city}|${suburb}|${province}`;
    if (initedFor.current === sessionKey) return;
    initedFor.current = sessionKey;

    // Reset UI state on each fresh open
    setSearch("");
    setContextLabel("");
    setLocating(false);

    // 1. Existing coords win — show them immediately, no geocode needed
    if (parsedInitial) {
      setCenter(parsedInitial);
      setZoom(16);
      setPin(parsedInitial);
      return;
    }

    // Otherwise: render the map at Port Moresby fallback IMMEDIATELY so the
    // user can interact even if geocoding fails. Clear any stale pin.
    setPin(null);
    setCenter({ lat: PORT_MORESBY.lat, lng: PORT_MORESBY.lng });
    setZoom(PORT_MORESBY.zoom);

    // Build the priority-ordered geocode queries
    const queries = [];
    if (suburb && city) queries.push({ q: `${suburb}, ${city}, ${province || ""}, Papua New Guinea`.replace(/,\s*,/g, ","), z: 15, label: `${suburb}, ${city}` });
    if (city) queries.push({ q: `${city}, ${province || ""}, Papua New Guinea`.replace(/,\s*,/g, ","), z: 13, label: city });
    if (province) queries.push({ q: `${province}, Papua New Guinea`, z: 10, label: province });

    if (queries.length === 0) return; // nothing to geocode; PoM is already set

    let cancelled = false;
    setLocating(true);
    (async () => {
      for (const { q, z, label } of queries) {
        const hit = await geocodeNominatim(q);
        if (cancelled) return;
        if (hit) {
          setCenter(hit);
          setZoom(z);
          setContextLabel(label);
          break;
        }
      }
      if (!cancelled) setLocating(false);
    })();
    return () => { cancelled = true; setLocating(false); };
  }, [open, initialCoords, city, suburb, province, parsedInitial]);

  // Reset session key when dialog closes so next open re-evaluates
  useEffect(() => { if (!open) initedFor.current = null; }, [open]);

  const doSearch = async () => {
    if (!search.trim()) return;
    setSearching(true);
    const hit = await geocodeNominatim(`${search}, Papua New Guinea`);
    setSearching(false);
    if (!hit) {
      toast.error("No results found");
      return;
    }
    setCenter(hit);
    setZoom(15);
    setPin(hit);
  };

  const confirm = () => {
    if (!pin) return;
    const value = `${pin.lat.toFixed(6)},${pin.lng.toFixed(6)}`;
    onConfirm?.(value);
    onOpenChange?.(false);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      data-testid="map-picker-dialog"
      onClick={(e) => { if (e.target === e.currentTarget) onOpenChange?.(false); }}
    >
      <div className="bg-white w-full h-full sm:h-[85vh] sm:w-[640px] sm:rounded-xl overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-white sticky top-0">
          <h3 className="font-semibold text-ink-900 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-[#0d50e0]" />
            Pick location on map
          </h3>
          <button
            type="button"
            onClick={() => onOpenChange?.(false)}
            className="p-1 rounded hover:bg-sand-100"
            aria-label="Close"
            data-testid="map-picker-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search bar */}
        <div className="px-4 py-2 border-b flex gap-2 bg-sand-50">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); doSearch(); } }}
              placeholder="Search town, suburb, or landmark…"
              className="w-full pl-8 pr-2 py-2 text-sm border rounded bg-white outline-none focus:ring-1 focus:ring-[#0d50e0]"
              data-testid="map-picker-search-input"
            />
          </div>
          <button
            type="button"
            onClick={doSearch}
            disabled={searching || !search.trim()}
            className="px-3 py-2 rounded text-sm bg-[#0d50e0] hover:bg-[#0b44c2] text-white disabled:opacity-50 disabled:cursor-not-allowed"
            data-testid="map-picker-search-btn"
          >
            {searching ? "…" : "Search"}
          </button>
        </div>

        {/* Context badge */}
        {contextLabel && !parsedInitial && (
          <div className="px-4 py-1.5 text-xs text-muted-foreground bg-sand-50 border-b flex items-center gap-1" data-testid="map-picker-context">
            <MapPin className="w-3 h-3 text-[#0d50e0]" />
            Centered on: <span className="font-medium">{contextLabel}</span>
          </div>
        )}

        {/* Map area — always renders; geocoding overlay is non-blocking */}
        <div className="relative flex-1 min-h-[320px] sm:min-h-[420px]" data-testid="map-picker-map">
          {locating && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[500] px-3 py-1 rounded-full bg-white/95 shadow text-xs text-muted-foreground border" data-testid="map-picker-locating">
              Locating area…
            </div>
          )}
          {center && (
            <MapContainer
              center={[center.lat, center.lng]}
              zoom={zoom}
              scrollWheelZoom
              className="h-full w-full"
              style={{ height: "100%", width: "100%" }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{y}/{x}.png"
              />
              <Recenter center={center} zoom={zoom} />
              <ClickToPlace onPick={setPin} />
              {pin && (
                <Marker
                  position={[pin.lat, pin.lng]}
                  draggable
                  eventHandlers={{
                    dragend: (e) => {
                      const ll = e.target.getLatLng();
                      setPin({ lat: ll.lat, lng: ll.lng });
                    },
                  }}
                />
              )}
            </MapContainer>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t bg-white flex flex-col-reverse sm:flex-row sm:items-center gap-2 sm:justify-between sticky bottom-0">
          <div className="text-xs" data-testid="map-picker-selected">
            {pin ? (
              <>
                <span className="text-muted-foreground">Selected:</span>{" "}
                <span className="font-mono text-ink-900">{pin.lat.toFixed(6)}, {pin.lng.toFixed(6)}</span>
              </>
            ) : (
              <span className="text-muted-foreground">Tap the map to drop a pin</span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onOpenChange?.(false)}
              className="px-4 py-2.5 min-h-[44px] rounded border text-sm hover:bg-sand-50"
              data-testid="map-picker-cancel"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirm}
              disabled={!pin}
              className="px-4 py-2.5 min-h-[44px] rounded text-sm bg-[#0d50e0] hover:bg-[#0b44c2] text-white disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="map-picker-confirm"
            >
              Use these coords
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
