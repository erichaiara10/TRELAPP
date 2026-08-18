import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, ArrowRight, ShieldCheck, MapPin, Briefcase, Users, Home as HomeIcon, Building2, Wallet, Wrench, ClipboardCheck, Plane, BarChart3 } from "lucide-react";
import { api } from "@/lib/api";
import { usePage } from "@/lib/usePage";
import PropertyCard from "@/components/PropertyCard";

const ICONS = { ShieldCheck, MapPin, Briefcase, Users, HomeIcon, Building2, Wallet, Wrench, ClipboardCheck, Plane, BarChart3, Home: HomeIcon };
function Icon({ name, ...props }) {
  const Cmp = ICONS[name] || ShieldCheck;
  return <Cmp {...props} />;
}

export default function Home() {
  const { sections } = usePage("home");
  const hero = sections.hero || {};
  const featIntro = sections.featured_intro || {};
  const whyUs = sections.why_us || {};
  const wantedT = sections.wanted_preview || {};
  const ctaBand = sections.cta_band || {};

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
        {hero.image && (
          <img src={hero.image} alt="" className="absolute inset-0 w-full h-full object-cover" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/40 to-black/20" />
        <div className="relative container-tight w-full pb-16 pt-20 text-white animate-fade-up">
          <div className="text-xs uppercase tracking-[0.3em] text-sand-100/80" data-testid="home-hero-kicker">{hero.kicker}</div>
          <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl leading-[1.05] mt-4 max-w-3xl" data-testid="home-hero-heading">
            {hero.heading}
          </h1>
          {hero.sub && <p className="mt-4 max-w-xl text-sand-100/90 text-base sm:text-lg whitespace-pre-line" data-testid="home-hero-sub">{hero.sub}</p>}

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

          {(hero.cta_primary?.label || hero.cta_secondary?.label) && (
            <div className="mt-6 flex flex-wrap gap-3 text-sm">
              {hero.cta_primary?.label && (
                <Link to={hero.cta_primary.href || "/buy"} data-testid="home-cta-primary"
                  className="px-5 py-2 rounded-full bg-white text-ink-900 hover:bg-sand-50 font-medium">
                  {hero.cta_primary.label}
                </Link>
              )}
              {hero.cta_secondary?.label && (
                <Link to={hero.cta_secondary.href || "/rent"} data-testid="home-cta-secondary"
                  className="px-5 py-2 rounded-full bg-white/10 hover:bg-white/20 text-white font-medium border border-white/30">
                  {hero.cta_secondary.label}
                </Link>
              )}
              <Link to="/price-compare" data-testid="home-cta-price-compare"
                className="px-5 py-2 rounded-full bg-[#F1B24A] text-ink-900 hover:brightness-105 font-medium flex items-center gap-2">
                <BarChart3 className="w-4 h-4" /> Get Free Price Guidance
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* FEATURED */}
      <section className="container-tight py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">{featIntro.kicker}</div>
            <h2 className="font-serif text-3xl sm:text-4xl mt-2">{featIntro.heading}</h2>
            {featIntro.sub && <p className="mt-2 text-ink-700 max-w-2xl text-sm">{featIntro.sub}</p>}
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
      {(whyUs.items?.length || 0) > 0 && (
        <section className="bg-pine-500 text-white py-16" data-testid="home-why-us">
          <div className="container-tight">
            <div className="max-w-2xl">
              <h2 className="font-serif text-3xl sm:text-4xl mt-2">{whyUs.heading}</h2>
            </div>
            <div className="mt-10 grid md:grid-cols-3 gap-6">
              {whyUs.items.map((it, i) => (
                <div key={i} className="rounded-2xl bg-white/5 backdrop-blur p-6 border border-white/10" data-testid={`home-why-us-${i}`}>
                  <Icon name={it.icon} className="w-6 h-6 mb-3" />
                  <div className="font-serif text-xl">{it.title}</div>
                  <p className="text-sm text-sand-100/80 mt-2 whitespace-pre-line">{it.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Property Wanted */}
      <section className="container-tight py-16">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">{wantedT.kicker}</div>
            <h2 className="font-serif text-3xl sm:text-4xl mt-2">{wantedT.heading}</h2>
            {wantedT.sub && <p className="mt-2 text-ink-700 max-w-2xl text-sm">{wantedT.sub}</p>}
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
      {(ctaBand.heading || ctaBand.sub) && (
        <section className="container-tight pb-20">
          <div className="rounded-3xl bg-ink-900 text-white p-10 md:p-14 relative overflow-hidden">
            <div className="max-w-2xl">
              <h2 className="font-serif text-3xl sm:text-4xl">{ctaBand.heading}</h2>
              {ctaBand.sub && <p className="text-sand-100/80 mt-3 whitespace-pre-line">{ctaBand.sub}</p>}
              <div className="mt-6 flex flex-col sm:flex-row gap-3">
                <Link to="/contact" data-testid="home-cta-band-btn" className="px-6 py-3 rounded-full bg-terracotta-500 hover:bg-terracotta-600 text-white font-medium text-center">
                  {ctaBand.button_label || "Get in touch"}
                </Link>
                <Link to="/add-property" data-testid="cta-add-property" className="px-6 py-3 rounded-full bg-white/10 hover:bg-white/20 text-white font-medium text-center">
                  Add Property
                </Link>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
