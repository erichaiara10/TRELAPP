import React from "react";
import { Link } from "react-router-dom";
import { Facebook, Home, Linkedin, Youtube } from "lucide-react";

export default function PublicFooter({ site }) {
  return <footer className="mt-4 border-t border-slate-200 bg-white text-slate-700" data-testid="public-footer">
    <div className="container-tight flex flex-col items-center justify-between gap-6 py-7 md:flex-row">
      <div className="flex items-center gap-2 text-[#0398FC]" aria-label={site.agency_name}><Home className="h-9 w-9" /><span className="text-2xl font-bold tracking-wide">TRELPNG</span></div>
      <nav className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm">
        <Link to="/about" className="hover:text-sky-600">About</Link><Link to="/contact" className="hover:text-sky-600">Contact</Link><Link to="/privacy" className="hover:text-sky-600">Privacy Policy</Link><Link to="/terms" className="hover:text-sky-600">Terms of Use</Link>
      </nav>
      <div className="flex items-center gap-4 text-[#0398FC]"><Facebook className="h-6 w-6" /><Linkedin className="h-6 w-6" /><Youtube className="h-7 w-7" /></div>
    </div>
    <div className="container-tight border-t border-slate-100 py-3 text-center text-xs text-slate-500">© {new Date().getFullYear()} TRELPNG. All rights reserved.</div>
  </footer>;
}
