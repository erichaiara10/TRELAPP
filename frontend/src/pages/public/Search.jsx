import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { usePage } from "@/lib/usePage";
import PropertyCard from "@/components/PropertyCard";
import { SlidersHorizontal, Search as SearchIcon } from "lucide-react";
import { usePropertyTypes } from "@/lib/usePropertyTypes";

export default function Search({ mode }) {
  const pageSlug = mode === "sale" ? "buy" : "rent";
  const { sections } = usePage(pageSlug);
  const { types } = usePropertyTypes();
  const hero = sections.hero || {};

  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState(params.get("q") || "");
  const [propertyType, setPropertyType] = useState(params.get("property_type") || "");
  const [location, setLocation] = useState(params.get("location") || "");
  const [minPrice, setMinPrice] = useState(params.get("min_price") || "");
  const [maxPrice, setMaxPrice] = useState(params.get("max_price") || "");
  const [beds, setBeds] = useState(params.get("bedrooms") || "");

  const fetchData = () => {
    setLoading(true);
    api.get("/properties", { params: {
      listing_type: mode, q: q || undefined, property_type: propertyType || undefined,
      location: location || undefined, min_price: minPrice || undefined,
      max_price: maxPrice || undefined, bedrooms: beds || undefined,
    }}).then((r) => setItems(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { fetchData(); /* eslint-disable-next-line */ }, [mode]);

  const submit = (e) => {
    e.preventDefault();
    const p = { q, property_type: propertyType, location, min_price: minPrice, max_price: maxPrice, bedrooms: beds };
    Object.keys(p).forEach((k) => !p[k] && delete p[k]);
    setParams(p);
    fetchData();
  };

  return (
    <div className="container-tight py-10">
      {/* Optional hero image + copy */}
      {(hero.image || hero.heading || hero.intro) && (
        <div className="relative rounded-2xl overflow-hidden mb-8 min-h-[220px]" data-testid={`${pageSlug}-hero`}>
          {hero.image && (
            <>
              <img src={hero.image} alt="" className="absolute inset-0 w-full h-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-black/10" />
            </>
          )}
          <div className={`relative p-8 md:p-10 ${hero.image ? "text-white" : "text-ink-900"}`}>
            {hero.kicker && <div className={`text-xs uppercase tracking-[0.3em] ${hero.image ? "text-sand-100/80" : "text-muted-foreground"}`}>{hero.kicker}</div>}
            <h1 className="font-serif text-3xl sm:text-4xl mt-2" data-testid={`${pageSlug}-hero-heading`}>
              {hero.heading || (mode === "sale" ? "Properties for sale" : "Properties for rent")}
            </h1>
            {hero.intro && <p className={`mt-3 max-w-2xl text-sm ${hero.image ? "text-sand-100/90" : "text-ink-700"}`}>{hero.intro}</p>}
          </div>
        </div>
      )}
      {!(hero.image || hero.heading || hero.intro) && (
        <div className="flex items-center gap-3 mb-6">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Browse</div>
            <h1 className="font-serif text-3xl sm:text-4xl mt-1">{mode === "sale" ? "Properties for sale" : "Properties for rent"}</h1>
          </div>
        </div>
      )}

      <form onSubmit={submit} className="bg-white rounded-2xl border border-border p-4 grid grid-cols-2 md:grid-cols-6 gap-3 mb-8" data-testid="search-filters">
        <div className="col-span-2 md:col-span-2 flex items-center gap-2 border border-border rounded-lg px-3">
          <SearchIcon className="w-4 h-4 text-muted-foreground" />
          <input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="filter-q" className="py-2 outline-none w-full bg-transparent" />
        </div>
        <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)} data-testid="filter-type" className="border border-border rounded-lg px-3 py-2 bg-white">
          <option value="">Any type</option>
          {(types || []).map((t) => (
            <option key={t.id} value={t.name}>{t.name}</option>
          ))}
        </select>
        <select value={location} onChange={(e) => setLocation(e.target.value)} data-testid="filter-location" className="border border-border rounded-lg px-3 py-2 bg-white">
          <option value="">All locations</option><option>Port Moresby</option><option>Lae</option><option>Madang</option><option>Mount Hagen</option><option>Kokopo</option>
        </select>
        <input type="number" placeholder="Min price" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} data-testid="filter-min" className="border border-border rounded-lg px-3 py-2 bg-white" />
        <input type="number" placeholder="Max price" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} data-testid="filter-max" className="border border-border rounded-lg px-3 py-2 bg-white" />
        <select value={beds} onChange={(e) => setBeds(e.target.value)} data-testid="filter-beds" className="border border-border rounded-lg px-3 py-2 bg-white">
          <option value="">Any beds</option><option value="1">1+</option><option value="2">2+</option><option value="3">3+</option><option value="4">4+</option>
        </select>
        <button type="submit" data-testid="filter-apply" className="col-span-2 md:col-span-1 px-4 py-2 rounded-lg bg-pine-500 hover:bg-pine-600 text-white flex items-center justify-center gap-2">
          <SlidersHorizontal className="w-4 h-4" /> Apply
        </button>
      </form>

      {loading && <div className="text-muted-foreground text-sm">Loading…</div>}
      {!loading && items.length === 0 && <div className="text-muted-foreground text-sm">No properties match your filters.</div>}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {items.map((p) => <PropertyCard key={p.id} p={p} />)}
      </div>
    </div>
  );
}
