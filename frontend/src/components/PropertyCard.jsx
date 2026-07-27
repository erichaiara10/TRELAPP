import React from "react";
import { Link } from "react-router-dom";
import { Bed, Bath, Car, MapPin, ShieldCheck, ExternalLink, Info } from "lucide-react";
import { money } from "@/lib/api";
import AIPriceAnalysis from "@/components/AIPriceAnalysis";
import { mapsUrlFromCoords } from "@/components/MapCoordsField";

const FALLBACK_IMG = "https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg";

function PropertySpecs({ p }) {
  return (
    <div className="mt-4 flex items-center gap-4 text-sm text-ink-700">
      {p.bedrooms > 0 && <span className="flex items-center gap-1"><Bed className="w-4 h-4" />{p.bedrooms}</span>}
      {p.bathrooms > 0 && <span className="flex items-center gap-1"><Bath className="w-4 h-4" />{p.bathrooms}</span>}
      {p.parking > 0 && <span className="flex items-center gap-1"><Car className="w-4 h-4" />{p.parking}</span>}
      {p.area_sqm && <span className="ml-auto text-xs text-muted-foreground">{p.area_sqm} sqm</span>}
    </div>
  );
}

function PropertyBadges({ p }) {
  return (
    <div className="absolute top-3 left-3 flex gap-2">
      <span className="px-2.5 py-1 text-xs rounded-full bg-white/95 text-ink-900 font-medium capitalize">
        {p.listing_type === "sale" ? "For Sale" : "For Rent"}
      </span>
      {p.featured && <span className="px-2.5 py-1 text-xs rounded-full bg-terracotta-500 text-white font-medium">Featured</span>}
    </div>
  );
}

export default function PropertyCard({ p }) {
  const isRent = p.listing_type === "rent";
  const mapHref = mapsUrlFromCoords(p.map_coords);
  return (
    <div data-testid={`property-card-${p.id}`}
      className="group relative bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300">
      <Link to={`/property/${p.id}`} className="block">
        <div className="relative aspect-[4/3] overflow-hidden bg-sand-100">
          <img src={p.images?.[0] || FALLBACK_IMG} alt={p.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
          <PropertyBadges p={p} />
          {p.verified && (
            <div className="absolute bottom-3 left-3 flex items-center gap-1 px-2 py-1 rounded-full bg-pine-500/95 text-white text-[11px]">
              <ShieldCheck className="w-3 h-3" /> Verified
            </div>
          )}
        </div>
        <div className="px-5 pt-5 pb-2">
          <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
            <MapPin className="w-3.5 h-3.5" /> {p.suburb ? `${p.suburb}, ` : ""}{p.location}
          </div>
          <h3 className="font-serif text-xl leading-snug text-ink-900 line-clamp-2 group-hover:text-pine-500">
            {p.title}
          </h3>
        </div>
      </Link>

      {/* Price + AI badge — SIBLING to the <Link>. Right-aligned via justify-between (variant B1).
          Keeping interactive elements (AI button) outside the router Link avoids nested-anchor / iframe issues. */}
      <div className="px-5 pb-2">
        <div className="flex items-baseline justify-between gap-2 flex-wrap">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold text-pine-500">{money(p.price, p.currency || "PGK")}</span>
            {isRent && <span className="text-sm text-muted-foreground">/ month</span>}
          </div>
          <AIPriceAnalysis
            variant="compact"
            buyerFacing
            audience="buyer"
            property_type={p.property_type}
            listing_type={p.listing_type}
            price={p.price}
            province={p.province}
            city={p.location}
            suburb={p.suburb}
            bedrooms={p.bedrooms}
            street_name={p.street_name}
            nearby_landmark={p.nearby_landmark}
            testIdPrefix={`card-ai-${p.id}`}
          />
        </div>
        <PropertySpecs p={p} />
      </div>

      {/* Map link — sibling to <Link>, prevents nested-anchor bug (see PropertyDetail history). */}
      <div className="px-5 pb-5">
        {mapHref ? (
          <a
            href={mapHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-pine-500 hover:bg-pine-600 text-white text-xs font-medium"
            data-testid={`card-map-btn-${p.id}`}
          >
            View on Google Maps <ExternalLink className="w-3 h-3" />
          </a>
        ) : (
          <div
            role="note"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-dashed border-border text-[11px] text-muted-foreground"
            data-testid={`card-map-empty-${p.id}`}
          >
            <Info className="w-3 h-3" />
            Google location not registered for this property
          </div>
        )}
      </div>
    </div>
  );
}
