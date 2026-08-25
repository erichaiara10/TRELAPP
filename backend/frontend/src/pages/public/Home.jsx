import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, MapPin, Home as HomeIcon, Bed, Bath, Car, Ruler, Users, ArrowRight, RefreshCw } from "lucide-react";
import { api, money } from "@/lib/api";
import PriceCompareButton from "@/components/PriceCompareButton";

const H01_HERO = "/images/h01-authoritative-hero.png";
const FALLBACK_PROPERTY = "https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg";

function ListingCard({ property }) {
  const rent = property.listing_type === "rent";
  return <article className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden" data-testid={`featured-property-${property.id}`}>
    <Link to={`/property/${property.id}`} className="block group">
      <div className="relative aspect-[16/8.5] overflow-hidden bg-slate-100">
        <img src={property.images?.[0] || FALLBACK_PROPERTY} alt={property.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
        <span className="absolute top-3 left-3 rounded-lg bg-white/95 px-2.5 py-1 text-xs text-[#075C36] font-semibold">{rent ? "For Rent" : "For Sale"}</span>
      </div>
      <div className="p-4">
        <div className="flex items-center gap-1 text-xs text-slate-600"><MapPin className="w-3.5 h-3.5" />{[property.suburb, property.location].filter(Boolean).join(", ")}</div>
        <h3 className="mt-2 text-lg font-semibold leading-snug line-clamp-1">{property.title}</h3>
        <div className="mt-1 text-lg font-bold text-[#075C36]">{property.price_label||money(property.price, property.currency || "PGK")}{rent&&(!property.price_type||property.price_type==="PGK") ? " / month" : ""}</div>
        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-600">
          <span className="flex gap-1"><Bed className="w-4 h-4" />{property.bedrooms ? `${property.bedrooms} Bedrooms` : "-"}</span><span className="flex gap-1"><Bath className="w-4 h-4" />{property.bathrooms ? `${property.bathrooms} Bathrooms` : "-"}</span>
          <span className="flex gap-1"><Car className="w-4 h-4" />{property.parking ? `${property.parking} Parking` : "-"}</span><span className="flex gap-1"><Ruler className="w-4 h-4" />{property.area_sqm ? `${property.area_sqm} m²` : "-"}</span>
        </div>
      </div>
    </Link>
    <div className="px-4 pb-4 grid grid-cols-2 gap-3">
      <Link to={`/property/${property.id}`} className="rounded-lg border border-[#075C36] py-2 text-center text-sm text-[#075C36] font-medium">View Details</Link>
      <PriceCompareButton
        property={property}
        audience="buyer"
        testIdPrefix={`home-ai-${property.id}`}
        showIcon={false}
        buttonClassName="w-full inline-flex items-center justify-center rounded-lg py-2 text-center text-sm text-[#075C36] font-medium hover:bg-emerald-50 transition-colors"
        buttonStyle={{ backgroundColor: "transparent" }}
      />
    </div>
  </article>;
}

export default function Home() {
  const navigate = useNavigate();
  const [intent, setIntent] = useState("sale");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState({ locations: [], types: [], listings: [] });
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [featured, setFeatured] = useState([]);
  const [featuredIntent, setFeaturedIntent] = useState("sale");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestRef = useRef(0);

  const loadFeatured = useCallback(async (mode = featuredIntent) => {
    setLoading(true); setError("");
    try {
      const { data } = await api.get("/properties", { params: { listing_type: mode, status: "active", featured: true, limit: 12 } });
      setFeatured(Array.isArray(data) ? data.slice(0, 12) : []);
    } catch (_) { setError("Featured properties are temporarily unavailable."); }
    finally { setLoading(false); }
  }, [featuredIntent]);
  useEffect(() => { loadFeatured(featuredIntent); }, [featuredIntent, loadFeatured]);

  useEffect(() => {
    const text = query.trim();
    if (text.length < 2) { setSuggestions({ locations: [], types: [], listings: [] }); setSuggestOpen(false); return; }
    const requestId = ++requestRef.current;
    const timer = setTimeout(async () => {
      try {
        const [cities, suburbs, types, listings] = await Promise.all([
          api.get("/locations/cities"), api.get("/locations/suburbs"), api.get("/property-types"),
          api.get("/properties", { params: { q: text, listing_type: intent, status: "active", limit: 5 } }),
        ]);
        if (requestId !== requestRef.current) return;
        const match = (x) => String(x.name || "").toLowerCase().includes(text.toLowerCase());
        const locations = [...(suburbs.data || []).filter(match), ...(cities.data || []).filter(match)].slice(0, 5);
        setSuggestions({ locations, types: (types.data || []).filter(match).slice(0, 5), listings: (listings.data || []).slice(0, 5) });
        setSuggestOpen(true); setActiveSuggestion(-1);
      } catch (_) { if (requestId === requestRef.current) setSuggestOpen(false); }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, intent]);

  const flatSuggestions = useMemo(() => [
    ...suggestions.locations.map((item) => ({ kind: "location", item, label: item.name })),
    ...suggestions.types.map((item) => ({ kind: "property_type", item, label: item.name })),
    ...suggestions.listings.map((item) => ({ kind: "listing", item, label: item.title })),
  ], [suggestions]);

  const selectSuggestion = (suggestion) => {
    if (suggestion.kind === "listing") { navigate(`/property/${suggestion.item.id}`); return; }
    setQuery(suggestion.label); setSuggestOpen(false);
    const key = suggestion.kind === "location" ? "q" : "property_type";
    navigate(`/${intent === "sale" ? "buy" : "rent"}?${key}=${encodeURIComponent(suggestion.label)}`);
  };
  const submitSearch = (e) => { e.preventDefault(); navigate(`/${intent === "sale" ? "buy" : "rent"}?q=${encodeURIComponent(query.trim())}`); };
  const onSearchKeyDown = (e) => {
    if (!suggestOpen || !flatSuggestions.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveSuggestion((v) => Math.min(v + 1, flatSuggestions.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActiveSuggestion((v) => Math.max(v - 1, 0)); }
    if (e.key === "Enter" && activeSuggestion >= 0) { e.preventDefault(); selectSuggestion(flatSuggestions[activeSuggestion]); }
    if (e.key === "Escape") setSuggestOpen(false);
  };

  let suggestionIndex = -1;
  const group = (label, items, kind, Icon) => items.length ? <div>
    {items.map((item) => { suggestionIndex += 1; const index = suggestionIndex; return <button type="button" key={`${kind}-${item.id || item.name}`} role="option" aria-selected={activeSuggestion === index} onClick={() => selectSuggestion({ kind, item, label: item.name || item.title })} className={`w-full px-4 py-3 flex items-center gap-3 text-left border-b ${activeSuggestion === index ? "bg-emerald-50" : "bg-white hover:bg-slate-50"}`}>
      <Icon className="w-5 h-5 text-[#075C36]" /><span className="w-24 text-sm text-[#075C36]">{label}</span><span className="text-sm font-medium">{item.name || item.title}</span>
    </button>; })}
  </div> : null;

  return <div className="bg-white">
    <section className="relative min-h-[390px] md:min-h-[430px] flex items-center justify-center overflow-hidden">
      <img src={H01_HERO} alt="Papua New Guinea residential property" className="absolute inset-0 w-full h-full object-cover" />
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative z-10 w-full max-w-3xl px-5 text-white text-center">
        <h1 className="text-4xl md:text-5xl font-semibold leading-tight">Find a place you’re<br />proud to call home.</h1>
        <p className="mt-3 text-base">Browse quality properties for sale and rent across Papua New Guinea.</p>
        <form onSubmit={submitSearch} className="mt-4" data-testid="home-search-form">
          <div className="flex justify-center"><div className="bg-white rounded-full p-1 flex text-sm text-slate-900">
            <button type="button" onClick={() => setIntent("sale")} className={`px-5 py-2 rounded-full ${intent === "sale" ? "bg-[#075C36] text-white" : ""}`}>Buy</button>
            <button type="button" onClick={() => setIntent("rent")} className={`px-5 py-2 rounded-full ${intent === "rent" ? "bg-[#075C36] text-white" : ""}`}>Rent</button>
          </div></div>
          <div className="mt-2 relative text-slate-900">
            <div className="bg-white rounded-xl p-1.5 flex shadow-xl"><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onSearchKeyDown} onFocus={() => query.length >= 2 && setSuggestOpen(true)} aria-autocomplete="list" aria-expanded={suggestOpen} placeholder="Search suburb, city or property type" className="flex-1 px-4 py-2.5 outline-none rounded-lg" data-testid="hero-search-input" /><button className="bg-[#075C36] text-white rounded-lg px-8 font-semibold" data-testid="hero-search-btn">Search</button></div>
            {suggestOpen && flatSuggestions.length > 0 && <div role="listbox" className="absolute z-20 mt-1 w-full rounded-xl overflow-hidden bg-white shadow-2xl border text-left">
              {group("Location", suggestions.locations, "location", MapPin)}{group("Property type", suggestions.types, "property_type", HomeIcon)}{group("Current listing", suggestions.listings, "listing", HomeIcon)}
              <div className="px-4 py-2 text-xs text-slate-500">Suggestions from current TRELPNG listings</div>
            </div>}
          </div>
        </form>
      </div>
    </section>

    <section className="container-tight py-5" data-testid="featured-properties">
      <div className="flex flex-wrap items-end gap-8 mb-4"><h2 className="text-3xl font-semibold">Featured Properties</h2>
        <button onClick={() => setFeaturedIntent("sale")} className={`pb-1 ${featuredIntent === "sale" ? "text-[#075C36] border-b-2 border-[#075C36]" : ""}`}>For Sale</button>
        <button onClick={() => setFeaturedIntent("rent")} className={`pb-1 ${featuredIntent === "rent" ? "text-[#075C36] border-b-2 border-[#075C36]" : ""}`}>For Rent</button>
        <Link to={featuredIntent === "sale" ? "/buy" : "/rent"} className="ml-auto text-sm text-[#075C36] flex items-center gap-1">View all properties <ArrowRight className="w-4 h-4" /></Link>
      </div>
      {loading && <div className="grid md:grid-cols-3 gap-5" aria-label="Loading featured properties">{[1,2,3].map((i) => <div key={i} className="h-72 rounded-2xl bg-slate-100 animate-pulse" />)}</div>}
      {!loading && error && <div className="rounded-xl bg-red-50 p-5 text-red-800 flex justify-between">{error}<button onClick={() => loadFeatured()} className="inline-flex gap-1"><RefreshCw className="w-4 h-4" />Retry</button></div>}
      {!loading && !error && featured.length === 0 && <div className="rounded-xl bg-slate-50 p-8 text-center text-slate-600">No featured properties are available right now. Please view all properties or check again soon.</div>}
      {!loading && !error && <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">{featured.map((property) => <ListingCard key={property.id} property={property} />)}</div>}
    </section>

    <section className="container-tight pb-6">
      <div className="relative border rounded-2xl pt-5">
        <h2 className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 bg-white px-4 text-xl font-semibold whitespace-nowrap">How TRELPNG Helps</h2>
        <div className="grid md:grid-cols-3 divide-y md:divide-y-0 md:divide-x">
          {[{ icon: Search, title: "Search Properties", body: "Find the right property for sale or rent across PNG with ease.", to: "/buy" }, { icon: HomeIcon, title: "Add Property", body: "List your property quickly and reach thousands of buyers or tenants.", to: "/add-property" }, { icon: Users, title: "Connect with Buyers/Tenants", body: "Connect directly with interested buyers or tenants you can trust.", to: "/contact" }].map(({icon: Icon, title, body, to}) => <Link key={title} to={to} className="p-5 flex items-center gap-5"><span className="w-14 h-14 rounded-full bg-blue-100 text-[#168CF5] grid place-items-center"><Icon className="w-7 h-7" /></span><span><strong className="block text-lg">{title}</strong><span className="text-sm text-slate-600">{body}</span></span></Link>)}
        </div>
      </div>
    </section>
  </div>;
}
