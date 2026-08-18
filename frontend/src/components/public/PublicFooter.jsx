import React from "react";
import { Link } from "react-router-dom";
import { Facebook, Linkedin, Youtube } from "lucide-react";

function TrelFooterLogo() {
  return <svg viewBox="0 0 150 64" className="h-14 w-32" role="img" aria-label="TREL">
    <path d="M8 21h134M25 21 75 5l50 16M27 21v34h96V21M36 47h78" fill="none" stroke="#0398FC" strokeWidth="5" strokeLinejoin="round" />
    <text x="34" y="45" fill="#0398FC" fontSize="28" fontWeight="800" fontFamily="Arial, sans-serif">TREL</text>
  </svg>;
}

export default function PublicFooter({ site }) {
  return <footer className="mt-4 border-t border-slate-200 bg-white text-slate-700" data-testid="public-footer">
    <div className="container-tight flex flex-col items-center justify-between gap-6 py-7 md:flex-row">
      <TrelFooterLogo />
      <nav className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm">
        <Link to="/about" className="hover:text-sky-600">About</Link><Link to="/contact" className="hover:text-sky-600">Contact</Link><Link to="/privacy" className="hover:text-sky-600">Privacy Policy</Link><Link to="/terms" className="hover:text-sky-600">Terms of Use</Link>
      </nav>
      <div className="flex items-center gap-4 text-[#0398FC]"><Facebook className="h-6 w-6" /><Linkedin className="h-6 w-6" /><Youtube className="h-7 w-7" /></div>
    </div>
    <div className="container-tight border-t border-slate-100 py-3 text-center text-xs text-slate-500">© {new Date().getFullYear()} TRELPNG. All rights reserved.</div>
  </footer>;
}
