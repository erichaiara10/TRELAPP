import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Bath, Bed, Building2, Car, Home as HomeIcon, MapPin, Search, Sparkles, Users } from "lucide-react";
import { api, money } from "@/lib/api";
import { usePage } from "@/lib/usePage";

const FALLBACK_HERO = "https://images.pexels.com/photos/259588/pexels-photo-259588.jpeg";
const FALLBACK_PROPERTIES = [
  { id: "mock-gordons", title: "Family Home in Gordons", location: "Port Moresby", suburb: "Gordons", price: 780000, currency: "PGK", listing_type: "sale", bedrooms: 3, bathrooms: 2, parking: 2, area_sqm: 650, images: ["https://images.pexels.com/photos/106399/pexels-photo-106399.jpeg"] },
  { id: "mock-beachfront", title: "Modern 4BR Beachfront Villa", location: "Port Moresby", suburb: "Ela Beach", price: 1450000, currency: "PGK", listing_type: "sale", bedrooms: 4, bathrooms: 3.5, parking: 2, area_sqm: 1012, images: ["https://images.pexels.com/photos/261327/pexels-photo-261327.jpeg"] },
  { id: "mock-land", title: "Land 1200sqm, 9-Mile", location: "Port Moresby", suburb: "9-Mile", price: 220000, currency: "PGK", listing_type: "sale", bedrooms: 0, bathrooms: 0, parking: 0, area_sqm: 1200, images: ["https://images.pexels.com/photos/440731/pexels-photo-440731.jpeg"] },
];

function HomePropertyCard({ property }) {
  const isRent = property.listing_type === "rent";
  return <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div className="relative aspect-[2.15/1] overflow-hidden bg-slate-100">
      <img src={property.images?.[0] || FALLBACK_PROPERTIES[0].images[0]} alt={property.title} className="h-full w-full object-cover" />
      <span className="absolute left-3 top-3 rounded-lg bg-white/95 px-3 py-1 text-xs font-medium text-sky-700">{isRent ? "For Rent" : "For Sale"}</span>
    </div>
    <div className="px-4 py-3">
      <p className="flex items-center gap-1 text-xs text-slate-500"><MapPin className="h-3.5 w-3.5" />{property.suburb ? `${property.suburb}, ` : ""}{property.location}</p>
      <h3 className="mt-1 text-lg font-bold leading-tight text-slate-950">{property.title}</h3>
      <p className="mt-1 text-lg font-semibold text-sky-700">{money(property.price, property.currency || "PGK")}{isRent && <span className="text-xs font-normal text-slate-500"> / month</span>}</p>
      <div className="mt-3 flex min-h-6 items-center gap-4 border-b border-slate-100 pb-3 text-xs text-slate-600">
        <span className="flex items-center gap-1"><Bed className="h-4 w-4" />{property.bedrooms || "–"}{property.bedrooms ? " Bedrooms" : ""}</span>
        <span className="flex items-center gap-1"><Bath className="h-4 w-4" />{property.bathrooms || "–"}{property.bathrooms ? " Bathrooms" : ""}</span>
        <span className="flex items-center gap-1"><Car className="h-4 w-4" />{property.parking || "–"}{property.parking ? " Parking" : ""}</span>
        {property.area_sqm && <span className="ml-auto flex items-center gap-1"><Building2 className="h-4 w-4" />{Number(property.area_sqm).toLocaleString()} m²</span>}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <Link to={`/property/${property.id}`} className="rounded-md border border-[#0398FC] px-3 py-2 text-center text-sm font-medium text-slate-900">View Details</Link>
        <Link to={`/price-compare?property=${property.id}`} className="flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-sky-700"><Sparkles className="h-5 w-5" />Compare Price</Link>
      </div>
    </div>
  </article>;
}

export default function Home() {
  const { sections } = usePage("home");
  const hero = sections.hero || {};
  const [featured, setFeatured] = useState([]);
  const [q, setQ] = useState("Bor");
  const [type, setType] = useState("sale");
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/properties", { params: { limit: 30 } })
      .then((response) => setFeatured(response.data || []))
      .catch(() => {});
  }, []);
  const visibleProperties = useMemo(() => {
    const matching = featured
      .filter((property) => property.listing_type === type)
      .sort((first, second) => {
        if (Boolean(first.featured) !== Boolean(second.featured)) return first.featured ? -1 : 1;
        return new Date(second.published_at || second.created_at || 0) - new Date(first.published_at || first.created_at || 0);
      });
    return (matching.length > 0 ? matching : FALLBACK_PROPERTIES.filter((property) => property.listing_type === type)).slice(0, 3);
  }, [featured, type]);

  const submitSearch = (event) => { event.preventDefault(); navigate(`/${type === "sale" ? "buy" : "rent"}?q=${encodeURIComponent(q)}`); };

  return <div className="bg-white">
    <section className="relative min-h-[390px] overflow-hidden">
      <img src={hero.image || FALLBACK_HERO} alt="Papua New Guinea property" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-slate-950/35" />
      <div className="relative mx-auto max-w-3xl px-5 pb-10 pt-8 text-white sm:pt-9">
        <h1 className="text-center text-4xl font-bold leading-tight drop-shadow sm:text-5xl">Find a place you’re<br className="hidden sm:block" /> proud to call home.</h1>
        <p className="mt-3 text-center text-base drop-shadow">Browse quality properties for sale and rent across Papua New Guinea.</p>
        <form onSubmit={submitSearch} className="mt-5">
          <div className="mb-2 ml-0 flex w-fit rounded-full bg-white p-1 text-sm text-slate-800">
            <button type="button" onClick={() => setType("sale")} className={`rounded-full px-6 py-2 ${type === "sale" ? "bg-[#0398FC] font-semibold text-black" : ""}`}>Buy</button>
            <button type="button" onClick={() => setType("rent")} className={`rounded-full px-6 py-2 ${type === "rent" ? "bg-[#0398FC] font-semibold text-black" : ""}`}>Rent</button>
          </div>
          <div className="flex rounded-xl bg-white p-1.5 shadow-xl">
            <input value={q} onChange={(event) => setQ(event.target.value)} className="min-w-0 flex-1 px-4 text-base text-slate-900 outline-none" aria-label="Search properties" />
            <button type="submit" className="rounded-lg bg-[#0398FC] px-8 py-3 font-semibold text-black">Search</button>
          </div>
          {q && <div className="mt-1 overflow-hidden rounded-xl bg-white text-slate-800 shadow-2xl">
            <div className="flex items-center gap-4 border-b border-slate-200 px-4 py-3"><MapPin className="h-5 w-5 text-[#0398FC]" /><span className="w-28 text-sm font-medium text-sky-700">Location</span><span className="text-sm">Boroko, Port Moresby</span></div>
            <div className="flex items-center gap-4 border-b border-slate-200 px-4 py-3"><HomeIcon className="h-5 w-5 text-[#0398FC]" /><span className="w-28 text-sm font-medium text-sky-700">Property type</span><span className="text-sm">Houses for sale in Boroko</span></div>
            <div className="flex items-center gap-4 px-4 py-3"><span className="h-8 w-8 overflow-hidden rounded"><img src={FALLBACK_PROPERTIES[0].images[0]} alt="" className="h-full w-full object-cover" /></span><span className="w-28 text-sm font-medium text-sky-700">Current listing</span><span className="text-sm">Family home in Boroko</span></div>
            <p className="border-t border-slate-100 px-4 py-1 text-xs text-slate-400">Suggestions from current TRELPNG listings</p>
          </div>}
        </form>
      </div>
    </section>

    <section className="container-tight py-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-8"><h2 className="text-3xl font-bold text-slate-950">Featured Properties</h2><div className="flex gap-8 text-sm"><button type="button" onClick={() => setType("sale")} className={`pb-2 ${type === "sale" ? "border-b-2 border-[#0398FC] text-sky-700" : "text-slate-600"}`}>For Sale</button><button type="button" onClick={() => setType("rent")} className={`pb-2 ${type === "rent" ? "border-b-2 border-[#0398FC] text-sky-700" : "text-slate-600"}`}>For Rent</button></div></div>
        <Link to={type === "sale" ? "/buy" : "/rent"} className="flex items-center gap-1 text-sm text-sky-700">View all properties <ArrowRight className="h-4 w-4" /></Link>
      </div>
      <div className="mt-4 grid gap-5 lg:grid-cols-3">{visibleProperties.map((property) => <HomePropertyCard key={property.id} property={property} />)}</div>
    </section>

    <section className="container-tight pb-5">
      <div className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm">
        <h2 className="text-center text-xl font-bold text-slate-950">How TRELPNG Helps</h2>
        <div className="grid divide-y divide-slate-200 md:grid-cols-3 md:divide-x md:divide-y-0">
          {[{ icon: Search, title: "Search Properties", text: "Find the right property for sale or rent across PNG with ease." }, { icon: HomeIcon, title: "Add Property", text: "List your property quickly and reach thousands of buyers or tenants." }, { icon: Users, title: "Connect with Buyers/Tenants", text: "Connect directly with interested buyers or tenants you can trust." }].map((item) => {
            const HelpIcon = item.icon;
            return <div key={item.title} className="flex items-center gap-4 px-5 py-3"><span className="grid h-14 w-14 shrink-0 place-items-center rounded-full border-[7px] border-sky-100 bg-[#0398FC]"><HelpIcon className="h-6 w-6 text-white" /></span><div><h3 className="font-bold text-slate-950">{item.title}</h3><p className="mt-1 text-xs leading-5 text-slate-600">{item.text}</p></div></div>;
          })}
        </div>
      </div>
    </section>
  </div>;
}
