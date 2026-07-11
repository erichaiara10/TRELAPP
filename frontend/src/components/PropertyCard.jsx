import React from "react";
import { Link } from "react-router-dom";
import { Bed, Bath, Car, MapPin, ShieldCheck } from "lucide-react";
import { money } from "@/lib/api";

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
  return (
    <Link to={`/property/${p.id}`} data-testid={`property-card-${p.id}`}
      className="group block bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300">
      <div className="relative aspect-[4/3] overflow-hidden bg-sand-100">
        <img src={p.images?.[0] || FALLBACK_IMG} alt={p.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        <PropertyBadges p={p} />
        {p.verified && (
          <div className="absolute bottom-3 left-3 flex items-center gap-1 px-2 py-1 rounded-full bg-pine-500/95 text-white text-[11px]">
            <ShieldCheck className="w-3 h-3" /> Verified
          </div>
        )}
      </div>
      <div className="p-5">
        <div className="flex items-center gap-1 text-xs text-muted-foreground mb-2">
          <MapPin className="w-3.5 h-3.5" /> {p.suburb ? `${p.suburb}, ` : ""}{p.location}
        </div>
        <h3 className="font-serif text-xl leading-snug text-ink-900 line-clamp-2 group-hover:text-pine-500">
          {p.title}
        </h3>
        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-2xl font-semibold text-pine-500">{money(p.price, p.currency || "PGK")}</span>
          {isRent && <span className="text-sm text-muted-foreground">/ month</span>}
        </div>
        <PropertySpecs p={p} />
      </div>
    </Link>
  );
}
