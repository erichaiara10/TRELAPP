import React, { useState, useEffect } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { Menu, X, Phone, MessageCircle } from "lucide-react";
import { api } from "@/lib/api";

const nav = [
  { to: "/buy", label: "Buy" },
  { to: "/rent", label: "Rent" },
  { to: "/sell", label: "Sell" },
  { to: "/wanted", label: "Property Wanted" },
  { to: "/management", label: "Property Mgmt" },
  { to: "/corporate", label: "Corporate" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

export default function PublicLayout() {
  const [open, setOpen] = useState(false);
  const [site, setSite] = useState({ agency_name: "PNG Realty", phone: "+675 7100 0000", whatsapp: "6757100000", email: "hello@pngrealty.pg", address: "" });
  const loc = useLocation();

  useEffect(() => {
    api.get("/content/site").then((r) => r.data?.value && setSite((s) => ({ ...s, ...r.data.value }))).catch(() => {});
  }, []);
  useEffect(() => { setOpen(false); window.scrollTo({ top: 0 }); }, [loc.pathname]);

  return (
    <div className="min-h-screen flex flex-col bg-sand-50 text-ink-900">
      <header className="sticky top-0 z-40 glass border-b border-border" data-testid="public-header">
        <div className="container-tight flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2 group" data-testid="brand-home-link">
            <div className="w-9 h-9 rounded-full bg-pine-500 text-white grid place-items-center font-serif text-lg">P</div>
            <div>
              <div className="font-serif text-lg leading-none">{site.agency_name}</div>
              <div className="text-[10px] tracking-[0.25em] uppercase text-muted-foreground">Papua New Guinea</div>
            </div>
          </Link>
          <nav className="hidden lg:flex items-center gap-6 text-sm">
            {nav.map((n) => (
              <Link key={n.to} to={n.to} data-testid={`nav-${n.to.slice(1)}`} className="text-ink-700 hover:text-pine-500">
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="hidden md:flex items-center gap-2">
            <a href={`tel:${site.phone}`} className="text-sm text-ink-700 hover:text-pine-500 flex items-center gap-1.5" data-testid="header-phone">
              <Phone className="w-4 h-4" /> {site.phone}
            </a>
            <a href={`https://wa.me/${(site.whatsapp || "").replace(/\D/g, "")}`} target="_blank" rel="noreferrer"
              className="text-sm px-3 py-2 rounded-full bg-pine-500 text-white hover:bg-pine-600 flex items-center gap-1.5" data-testid="header-whatsapp">
              <MessageCircle className="w-4 h-4" /> WhatsApp
            </a>
          </div>
          <button className="lg:hidden p-2" onClick={() => setOpen(!open)} data-testid="mobile-menu-toggle" aria-label="Menu">
            {open ? <X /> : <Menu />}
          </button>
        </div>
        {open && (
          <div className="lg:hidden border-t border-border bg-white">
            <div className="container-tight py-3 flex flex-col gap-1">
              {nav.map((n) => (
                <Link key={n.to} to={n.to} data-testid={`mnav-${n.to.slice(1)}`} className="py-2 text-ink-700">
                  {n.label}
                </Link>
              ))}
              <a href={`tel:${site.phone}`} className="py-2 text-pine-500 flex items-center gap-2"><Phone className="w-4 h-4" />{site.phone}</a>
            </div>
          </div>
        )}
      </header>

      <main className="flex-1"><Outlet /></main>

      <footer className="bg-pine-700 text-sand-50 mt-12">
        <div className="container-tight py-12 grid md:grid-cols-4 gap-8">
          <div>
            <div className="font-serif text-2xl">{site.agency_name}</div>
            <p className="text-sm mt-2 text-sand-100/80">{site.tagline || "Homes rooted in the heart of Papua New Guinea"}</p>
            <p className="text-xs mt-4 text-sand-100/60">{site.address}</p>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-sand-100/70 mb-3">Explore</div>
            <ul className="space-y-1.5 text-sm">
              <li><Link to="/buy">Buy</Link></li><li><Link to="/rent">Rent</Link></li>
              <li><Link to="/sell">Sell</Link></li><li><Link to="/wanted">Property Wanted</Link></li>
            </ul>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-sand-100/70 mb-3">Services</div>
            <ul className="space-y-1.5 text-sm">
              <li><Link to="/management">Property Management</Link></li>
              <li><Link to="/corporate">Corporate Services</Link></li>
              <li><Link to="/about">About</Link></li>
              <li><Link to="/contact">Contact</Link></li>
            </ul>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-sand-100/70 mb-3">Contact</div>
            <ul className="space-y-1.5 text-sm">
              <li>{site.phone}</li>
              <li>{site.email}</li>
              <li><Link to="/admin/login" data-testid="footer-staff-login">Staff login</Link></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-sand-100/10">
          <div className="container-tight py-4 flex flex-col md:flex-row items-center justify-between gap-2 text-xs text-sand-100/60">
            <div>© {new Date().getFullYear()} {site.agency_name}. All rights reserved.</div>
            <div className="flex gap-4"><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link></div>
          </div>
        </div>
      </footer>
    </div>
  );
}
