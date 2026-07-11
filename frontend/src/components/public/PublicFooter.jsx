import React from "react";
import { Link } from "react-router-dom";

export default function PublicFooter({ site }) {
  return (
    <footer className="bg-pine-700 text-sand-50 mt-12">
      <div className="container-tight py-12 grid md:grid-cols-4 gap-8">
        <div>
          <div className="font-serif text-2xl">{site.agency_name}</div>
          <p className="text-sm mt-2 text-sand-100/80">{site.tagline || "We Care To Share"}</p>
          <p className="text-xs mt-4 text-sand-100/60 whitespace-pre-line">{site.address}</p>
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
  );
}
