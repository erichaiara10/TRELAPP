import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Phone, MessageCircle, PlusCircle } from "lucide-react";

const NAV = [
  { to: "/", label: "Home" }, { to: "/buy", label: "Buy" }, { to: "/rent", label: "Rent" },
  { to: "/wanted", label: "Property Wanted" }, { to: "/management", label: "Property Management" },
  { to: "/corporate", label: "Corporate Services" },
];
const DEFAULT_PHONE = "+675 76281552";
const DEFAULT_WHATSAPP = "+675 8138 3302";

function contactLinks(site) {
  const phone = String(site?.phone || DEFAULT_PHONE).trim();
  const whatsapp = String(site?.whatsapp || DEFAULT_WHATSAPP).replace(/\D/g, "");
  return {
    phone,
    phoneHref: `tel:${phone.replace(/[^\d+]/g, "")}`,
    whatsappHref: `https://wa.me/${whatsapp}`,
  };
}

function BrandLogo({ site }) {
  return <Link to="/" className="flex items-center gap-2 shrink-0" data-testid="brand-home-link" aria-label="TRELPNG Home">
    <img src={site.logo_url} alt="TREL logo" className="h-10 w-14 object-contain" />
    <span className="text-xl xl:text-2xl font-bold tracking-tight text-[#1597E5]">TRELPNG</span>
  </Link>;
}

function MenuLinks({ mobile = false }) {
  const loc = useLocation();
  return NAV.map((item) => {
    const active = item.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(item.to);
    return <Link key={item.to} to={item.to} data-testid={`${mobile ? "mnav" : "nav"}-${item.to === "/" ? "home" : item.to.slice(1)}`}
      className={`${mobile ? "py-2.5 border-b border-slate-100" : "h-16 inline-flex items-center whitespace-nowrap"} text-[12px] xl:text-[13px] font-medium ${active ? "text-[#075C36] border-b-2 border-[#075C36]" : "text-slate-800 hover:text-[#075C36]"}`}>
      {item.label}
    </Link>;
  });
}

export default function PublicHeader({ site }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const { phone, phoneHref, whatsappHref } = contactLinks(site);
  useEffect(() => { setOpen(false); window.scrollTo({ top: 0 }); }, [loc.pathname]);
  return <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200 shadow-sm" data-testid="public-header">
    <div className="max-w-[1500px] mx-auto px-4 flex items-center h-16 gap-3 xl:gap-5">
      <BrandLogo site={site} />
      <nav className="hidden lg:flex flex-1 items-center justify-center gap-3 xl:gap-5" aria-label="Primary navigation"><MenuLinks /></nav>
      <div className="hidden lg:flex items-center gap-2 xl:gap-3 shrink-0 text-[12px] xl:text-[13px]">
        <Link to="/add-property" data-testid="nav-add-property" className="inline-flex items-center gap-1.5 rounded-lg bg-[#168CF5] px-3 py-2.5 text-white font-semibold hover:bg-[#0878D8] whitespace-nowrap"><PlusCircle className="w-4 h-4" /> Add Property</Link>
        <Link to="/add-property?auth=login" data-testid="nav-login" className="font-medium whitespace-nowrap">Log In</Link>
        <Link to="/add-property?auth=register" data-testid="nav-register" className="font-medium whitespace-nowrap">Register</Link>
        <Link to="/about" data-testid="nav-about" className="font-medium whitespace-nowrap">About</Link>
        <Link to="/contact" data-testid="nav-contact" className="font-medium whitespace-nowrap">Contact</Link>
        <a href={phoneHref} className="inline-flex items-center gap-1 whitespace-nowrap" data-testid="header-phone"><Phone className="w-3.5 h-3.5" />{phone}</a>
        <a href={whatsappHref} target="_blank" rel="noopener noreferrer" data-testid="header-whatsapp" className="inline-flex items-center gap-1.5 rounded-full bg-[#176B4A] px-3 py-2 text-white font-semibold hover:bg-[#0D5639] whitespace-nowrap"><MessageCircle className="w-4 h-4" /> WhatsApp</a>
      </div>
      <button type="button" className="lg:hidden ml-auto p-2" onClick={() => setOpen((v) => !v)} data-testid="mobile-menu-toggle" aria-expanded={open} aria-controls="mobile-navigation" aria-label={open ? "Close menu" : "Open menu"}>{open ? <X /> : <Menu />}</button>
    </div>
    {open && <nav id="mobile-navigation" className="lg:hidden bg-white border-t px-5 pb-5 flex flex-col" aria-label="Mobile navigation">
      <MenuLinks mobile />
      <Link to="/add-property" data-testid="mnav-add-property" className="mt-3 py-2.5 px-3 rounded-lg bg-[#168CF5] text-white font-semibold inline-flex items-center gap-2"><PlusCircle className="w-4 h-4" />Add Property</Link>
      <Link to="/add-property?auth=login" data-testid="mnav-login" className="py-2.5 border-b">Log In</Link><Link to="/add-property?auth=register" data-testid="mnav-register" className="py-2.5 border-b">Register</Link>
      <Link to="/about" className="py-2.5 border-b">About</Link><Link to="/contact" className="py-2.5 border-b">Contact</Link>
      <a href={phoneHref} data-testid="mnav-phone" className="py-2.5 inline-flex items-center gap-2"><Phone className="w-4 h-4" />{phone}</a>
      <a href={whatsappHref} data-testid="mnav-whatsapp" target="_blank" rel="noopener noreferrer" className="py-2.5 inline-flex items-center gap-2 text-[#075C36]"><MessageCircle className="w-4 h-4" />WhatsApp</a>
    </nav>}
  </header>;
}
