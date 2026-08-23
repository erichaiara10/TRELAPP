import React from "react";
import { Link } from "react-router-dom";
import { Facebook, Linkedin, Youtube } from "lucide-react";

export default function PublicFooter({ site }) {
  return <footer className="bg-white border-t border-slate-200" data-testid="public-footer">
    <div className="container-tight py-5 flex flex-col lg:flex-row items-center justify-between gap-5">
      <Link to="/" aria-label="TRELPNG Home"><img src={site.logo_url} alt="TREL logo" className="h-14 w-auto object-contain" /></Link>
      <nav className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-sm" aria-label="Footer navigation">
        <Link to="/about" className="hover:text-[#075C36]">About</Link><Link to="/contact" className="hover:text-[#075C36]">Contact</Link>
        <Link to="/privacy" className="hover:text-[#075C36]">Privacy Policy</Link><Link to="/terms" className="hover:text-[#075C36]">Terms of Use</Link>
      </nav>
      <div className="flex gap-3" aria-label="Social media">
        {[Facebook, Linkedin, Youtube].map((Icon, i) => <span key={i} aria-disabled="true" className="w-9 h-9 rounded-full bg-slate-50 text-[#168CF5] grid place-items-center"><Icon className="w-5 h-5" /></span>)}
      </div>
    </div>
    <div className="pb-4 text-center text-xs text-slate-500">© 2025 TRELPNG. All rights reserved.</div>
  </footer>;
}
