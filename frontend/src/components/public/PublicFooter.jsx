import React from "react";
import { Link } from "react-router-dom";

const BRAND_BLUE = "#0d50e0";

export default function PublicFooter({ site }) {
  return (
    <footer className="text-white mt-12" style={{ backgroundColor: BRAND_BLUE }} data-testid="public-footer">
      <div className="container-tight py-12 grid md:grid-cols-4 gap-8">
        <div>
          <div className="font-serif text-2xl">{site.agency_name}</div>
          <p className="text-sm mt-2 text-white/90">{site.tagline || "We Care To Share"}</p>
          <p className="text-xs mt-4 text-white/80 whitespace-pre-line">{site.address}</p>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-white/70 mb-3">Explore</div>
          <ul className="space-y-1.5 text-sm">
            <li><Link to="/buy" className="hover:text-white/80">Buy</Link></li>
            <li><Link to="/rent" className="hover:text-white/80">Rent</Link></li>
            <li><Link to="/sell" className="hover:text-white/80">Sell</Link></li>
            <li><Link to="/wanted" className="hover:text-white/80">Property Wanted</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-white/70 mb-3">Services</div>
          <ul className="space-y-1.5 text-sm">
            <li><Link to="/management" className="hover:text-white/80">Property Management</Link></li>
            <li><Link to="/corporate" className="hover:text-white/80">Corporate Services</Link></li>
            <li><Link to="/about" className="hover:text-white/80">About</Link></li>
            <li><Link to="/contact" className="hover:text-white/80">Contact</Link></li>
          </ul>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.25em] text-white/70 mb-3">Contact</div>
          <ul className="space-y-1.5 text-sm">
            {site.phone && <li>{site.phone}</li>}
            {site.email && <li className="break-all">{site.email}</li>}
            <li><Link to="/admin/login" data-testid="footer-staff-login" className="hover:text-white/80">Staff login</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/20">
        <div className="container-tight py-4 flex flex-col md:flex-row items-center justify-between gap-2 text-xs text-white/80">
          <div>© {new Date().getFullYear()} {site.agency_name}. All rights reserved.</div>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-white">Privacy</Link>
            <Link to="/terms" className="hover:text-white">Terms</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
