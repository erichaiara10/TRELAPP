import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Phone, MessageCircle } from "lucide-react";

const NAV = [
  { to: "/buy", label: "Buy" },
  { to: "/rent", label: "Rent" },
  { to: "/sell", label: "Sell" },
  { to: "/wanted", label: "Property Wanted" },
  { to: "/management", label: "Property Mgmt" },
  { to: "/corporate", label: "Corporate" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
];

function BrandLogo({ site }) {
  const short = site.short_name || "TREL";
  if (site.logo_url) {
    return (
      <Link to="/" className="flex items-center gap-3 group shrink-0" data-testid="brand-home-link" aria-label={site.agency_name}>
        <img src={site.logo_url} alt={site.agency_name}
          className="h-12 w-auto object-contain" />
        <div className="hidden sm:block leading-tight">
          <div className="font-serif text-base text-ink-900">{site.agency_name}</div>
          <div className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground italic">{site.tagline || "We Care To Share"}</div>
        </div>
      </Link>
    );
  }
  return (
    <Link to="/" className="flex items-center gap-2 group" data-testid="brand-home-link">
      <div className="w-9 h-9 rounded-full bg-pine-500 text-white grid place-items-center font-serif text-lg">
        {short.slice(0, 1)}
      </div>
      <div>
        <div className="font-serif text-lg leading-none">{site.agency_name}</div>
        <div className="text-[10px] tracking-[0.25em] uppercase text-muted-foreground">Papua New Guinea</div>
      </div>
    </Link>
  );
}

export default function PublicHeader({ site }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); window.scrollTo({ top: 0 }); }, [loc.pathname]);

  const waNumber = (site.whatsapp || "").replace(/\D/g, "");

  return (
    <header className="sticky top-0 z-40 glass border-b border-border" data-testid="public-header">
      <div className="container-tight flex items-center justify-between h-16 gap-4">
        <BrandLogo site={site} />
        <nav className="hidden lg:flex items-center gap-5 text-sm">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} data-testid={`nav-${n.to.slice(1)}`} className="text-ink-700 hover:text-pine-500">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="hidden md:flex items-center gap-2 shrink-0">
          <a href={`tel:${site.phone}`} className="text-sm text-ink-700 hover:text-pine-500 flex items-center gap-1.5" data-testid="header-phone">
            <Phone className="w-4 h-4" /> {site.phone}
          </a>
          <a href={`https://wa.me/${waNumber}`} target="_blank" rel="noreferrer"
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
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} data-testid={`mnav-${n.to.slice(1)}`} className="py-2 text-ink-700">
                {n.label}
              </Link>
            ))}
            <a href={`tel:${site.phone}`} className="py-2 text-pine-500 flex items-center gap-2"><Phone className="w-4 h-4" />{site.phone}</a>
          </div>
        </div>
      )}
    </header>
  );
}
