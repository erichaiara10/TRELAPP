import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Plus } from "lucide-react";

const NAV = [
  { to: "/buy", label: "Buy" },
  { to: "/rent", label: "Rent" },
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
        <div className="hidden md:flex items-center gap-3 shrink-0">
          <Link to="/add-property?auth=login" className="text-sm font-medium text-ink-700 hover:text-sky-600" data-testid="header-login">Log In</Link>
          <Link to="/add-property?auth=register" className="text-sm font-medium text-ink-700 hover:text-sky-600" data-testid="header-register">Register</Link>
          <Link to="/add-property" className="flex items-center gap-2 rounded-lg bg-[#0398FC] px-4 py-2.5 text-sm font-semibold text-black hover:brightness-95" data-testid="header-add-property"><Plus className="h-4 w-4" /> Add Property</Link>
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
            <Link to="/add-property?auth=login" className="py-2 text-ink-700">Log In</Link>
            <Link to="/add-property?auth=register" className="py-2 text-ink-700">Register</Link>
            <Link to="/add-property" className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-[#0398FC] px-4 py-3 font-semibold text-black"><Plus className="h-4 w-4" /> Add Property</Link>
          </div>
        </div>
      )}
    </header>
  );
}
