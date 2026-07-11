import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, ArrowRight, ShieldCheck, Users, Home as HomeIcon } from "lucide-react";
import { api } from "@/lib/api";
import PropertyCard from "@/components/PropertyCard";

export default function Home() {
  const [featured, setFeatured] = useState([]);
  const [wanted, setWanted] = useState([]);
  const [q, setQ] = useState("");
  const [type, setType] = useState("sale");
  const nav = useNavigate();

  useEffect(() => {
    api.get("/properties", { params: { featured: true, limit: 6 } }).then((r) => setFeatured(r.data)).catch(() => {});
    api.get("/requirements/public").then((r) => setWanted(r.data)).catch(() => {});
  }, []);

  const doSearch = (e) => {
    e.preventDefault();
    nav(`/${type === "sale" ? "buy" : "rent"}?q=${encodeURIComponent(q)}`);
  };

  return (
    <div>
      {/* HERO */}
      <section className="relative min-h-[560px] flex items-end overflow-hidden">
        <img src="https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg"
          alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/40 to-black/20" />
        <div className="relative container-tight w-full pb-16 pt-20 text-white animate-fade-up">
          <div className="text-xs uppercase tracking-[0.3em] text-sand-100/80">Papua New Guinea Real Estate</div>
          <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl leading-[1.05] mt-4 max-w-3xl">
            Find a place<br />that belongs to you.
          </h1>
          <p className="mt-4 max-w-xl text-sand-100/90 text-base sm:text-lg">
            Verified homes, apartments, land and commercial properties across Port Moresby, Lae, Madang and beyond.
          </p>

          <form onSubmit={doSearch} className="mt-8 bg-white rounded-2xl p-2 sm:p-3 flex flex-col sm:flex-row gap-2 shadow-2xl max-w-3xl">
            <div className="flex rounded-full bg-sand-100 p-1 shrink-0">
              {["sale","rent"].map((t) => (
                <button type="button" key={t} onClick={() => setType(t)} data-testid={`hero-tab-${t}`}
                  className={`px-4 py-2 rounded-full text-sm font-medium ${type===t?"bg-pine-500 text-white":"text-ink-700"}`}>
                  {t==="sale"?"Buy":"Rent"}
                </button>
              ))}
            </div>
            <div className="flex-1 flex items-center gap-2 px-3">
              <Search className="w-5 h-5 text-muted-foreground" />
              <input value={q} onChange={(e) => setQ(e.target.value)} data-testid="hero-search-input"
                placeholder="Search suburb, city or keyword"
                className="w-full py-2.5 outline-none text-ink-900 placeholder:text-muted-foreground bg-transparent" />
            </div>
            <button type="submit" data-testid="hero-search-btn"
              className="px-6 py-3 rounded-full bg-pine-500 hover:bg-pine-600 text-white font-medium flex items-center justify-center gap-2">
              Search <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </section>

      {/* FEATURED */}
      <section className="container-tight py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Handpicked</div>
            <h2 className="font-serif text-3xl sm:text-4xl mt-2">Featured properties</h2>
          </div>
          <Link to="/buy" className="text-sm text-pine-500 hover:text-pine-600 flex items-center gap-1" data-testid="view-all-featured">
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {featured.map((p) => <PropertyCard key={p.id} p={p} />)}
          {featured.length === 0 && <div className="text-sm text-muted-foreground">Loading properties…</div>}
        </div>
      </section>

      {/* Why us */}
      <section className="bg-pine-500 text-white py-16">
        <div className="container-tight">
          <div className="max-w-2xl">
            <div className="text-xs uppercase tracking-[0.25em] text-sand-100/80">Why choose us</div>
            <h2 className="font-serif text-3xl sm:text-4xl mt-2">Built by locals, trusted by corporates.</h2>
          </div>
          <div className="mt-10 grid md:grid-cols-3 gap-6">
            {[
              { Icon: ShieldCheck, title: "Verified listings", body: "Every property is inspected and vetted by our team before it goes live." },
              { Icon: Users, title: "Local expertise", body: "Born and raised in PNG — we know every suburb, security landscape and school catchment." },
              { Icon: HomeIcon, title: "End-to-end service", body: "From your first enquiry to keys-in-hand, one team handles it all." },
            ].map(({ Icon, title, body }) => (
              <div key={title} className="rounded-2xl bg-white/5 backdrop-blur p-6 border border-white/10">
                <Icon className="w-6 h-6 mb-3" />
                <div className="font-serif text-xl">{title}</div>
                <p className="text-sm text-sand-100/80 mt-2">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Property Wanted */}
      <section className="container-tight py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Buyers &amp; tenants looking</div>
            <h2 className="font-serif text-3xl sm:text-4xl mt-2">Property Wanted</h2>
          </div>
          <Link to="/wanted" className="text-sm text-pine-500 hover:text-pine-600 flex items-center gap-1" data-testid="view-all-wanted">
            Submit your requirement <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="grid md:grid-cols-2 gap-6">
          {wanted.slice(0, 4).map((w, i) => (
            <div key={i} className="bg-white rounded-2xl p-6 border border-border" data-testid={`wanted-card-${i}`}>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 text-xs rounded-full bg-terracotta-50 text-terracotta-600 capitalize">{w.intent}</span>
                <span className="px-2 py-0.5 text-xs rounded-full bg-sand-100 text-ink-700 capitalize">{w.property_type || "any"}</span>
                {w.is_corporate && <span className="px-2 py-0.5 text-xs rounded-full bg-pine-500 text-white">Corporate</span>}
              </div>
              <h3 className="font-serif text-xl mt-3">
                {w.intent === "buy" ? "Looking to buy" : "Looking to rent"} up to {(w.max_price || 0).toLocaleString()} PGK
              </h3>
              <p className="text-sm text-muted-foreground mt-2 line-clamp-3">{w.notes}</p>
              <div className="mt-3 text-xs text-muted-foreground">
                {(w.locations || []).join(", ") || "Any location"} · {w.min_bedrooms}+ beds
              </div>
            </div>
          ))}
          {wanted.length === 0 && <div className="text-sm text-muted-foreground">No active requirements listed.</div>}
        </div>
      </section>

      {/* CTA */}
      <section className="container-tight pb-20">
        <div className="rounded-3xl bg-ink-900 text-white p-10 md:p-14 relative overflow-hidden">
          <div className="max-w-2xl">
            <h2 className="font-serif text-3xl sm:text-4xl">Selling, leasing or need management?</h2>
            <p className="text-sand-100/80 mt-3">List with PNG Realty and get a dedicated agent, professional marketing, and access to our corporate buyer network.</p>
            <div className="mt-6 flex flex-col sm:flex-row gap-3">
              <Link to="/sell" data-testid="cta-sell" className="px-6 py-3 rounded-full bg-terracotta-500 hover:bg-terracotta-600 text-white font-medium text-center">
                Submit your property
              </Link>
              <Link to="/management" data-testid="cta-management" className="px-6 py-3 rounded-full bg-white/10 hover:bg-white/20 text-white font-medium text-center">
                Property management
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
