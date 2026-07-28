import React, { useEffect, useMemo, useState } from "react";
import LeadFormPage from "./LeadFormPage";
import { api } from "@/lib/api";
import { usePage } from "@/lib/usePage";
import { Phone, Mail, MapPin, MessageCircle, ExternalLink, Clock } from "lucide-react";
import { MAPS_BASE, mapsUrlFromCoords } from "@/components/MapCoordsField";

export default function Contact() {
  const { sections } = usePage("contact");
  const hero = sections.hero || {};
  const businessHours = sections.business_hours || "";
  const contactCoords = sections.map_coords || "";

  const [site, setSite] = useState({ phone: "", email: "", whatsapp: "", address: "", map_coords: "" });
  useEffect(() => {
    api.get("/content/site").then((r) => r.data?.value && setSite((s) => ({ ...s, ...r.data.value }))).catch(() => {});
  }, []);

  const waNumber = (site.whatsapp || "").replace(/\D/g, "");
  const waLink = waNumber ? `https://wa.me/${waNumber}` : "#";
  const telLink = site.phone ? `tel:${site.phone.replace(/\s+/g, "")}` : "#";
  const mailLink = site.email ? `mailto:${site.email}` : "#";

  // Compose ONE Google Maps URL — prefer coords, else search by address.
  // We intentionally do NOT use an iframe embed because Google's headers block
  // it on many browsers ("refused to connect"). The user opens the map in a new tab.
  const mapOpen = useMemo(() => {
    const coords = (contactCoords || site.map_coords || "").trim();
    if (coords) return mapsUrlFromCoords(coords);
    const addr = (site.address || "Port Moresby, Papua New Guinea").trim();
    return `${MAPS_BASE}${encodeURIComponent(addr)}`;
  }, [contactCoords, site.map_coords, site.address]);

  return (
    <div>
      <div className="container-tight pt-14 grid md:grid-cols-2 gap-10">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground" data-testid="contact-hero-kicker">{hero.kicker || "CONTACT"}</div>
          <h1 className="font-serif text-4xl sm:text-5xl mt-3" data-testid="contact-hero-heading">{hero.heading || "Get in touch"}</h1>
          {hero.intro && <p className="text-ink-700 mt-4 whitespace-pre-line" data-testid="contact-hero-intro">{hero.intro}</p>}

          {/* Contact details */}
          <div className="mt-8 space-y-3 text-sm">
            {businessHours && (
              <div className="flex items-center gap-2" data-testid="contact-hours-line">
                <Clock className="w-4 h-4 text-pine-500" />{businessHours}
              </div>
            )}
            {site.phone && (
              <div className="flex items-center gap-2" data-testid="contact-phone-line">
                <Phone className="w-4 h-4 text-pine-500" />{site.phone}
              </div>
            )}
            {site.email && (
              <div className="flex items-center gap-2 break-all" data-testid="contact-email-line">
                <Mail className="w-4 h-4 text-pine-500" />{site.email}
              </div>
            )}
            {site.address && (
              <div className="flex items-start gap-2" data-testid="contact-address-line">
                <MapPin className="w-4 h-4 text-pine-500 mt-0.5 shrink-0" />
                <span className="whitespace-pre-line">{site.address}</span>
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-2" data-testid="contact-action-buttons">
            <a href={telLink} data-testid="contact-call-btn"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-full bg-pine-500 hover:bg-pine-600 text-white text-sm font-medium">
              <Phone className="w-4 h-4" /> Call Now
            </a>
            <a href={mailLink} data-testid="contact-email-btn"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-full bg-ink-900 hover:bg-ink-700 text-white text-sm font-medium">
              <Mail className="w-4 h-4" /> Email Us
            </a>
            <a href={waLink} target="_blank" rel="noreferrer" data-testid="contact-whatsapp-btn"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-full bg-terracotta-500 hover:bg-terracotta-600 text-white text-sm font-medium">
              <MessageCircle className="w-4 h-4" /> WhatsApp Chat
            </a>
          </div>

          {/* Google Maps — button opens in a new tab (no iframe: Google blocks embeds via X-Frame-Options / CSP). */}
          <div className="mt-8">
            <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground mb-3">Our office</div>
            <a
              href={mapOpen}
              target="_blank"
              rel="noreferrer"
              data-testid="contact-view-map-btn"
              className="group relative flex items-center gap-4 rounded-2xl overflow-hidden border border-border bg-white p-5 hover:border-pine-500 hover:shadow-md transition-all"
            >
              <div className="w-14 h-14 shrink-0 rounded-xl bg-pine-500 text-white grid place-items-center">
                <MapPin className="w-6 h-6" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-ink-900">View on Google Maps</div>
                <div className="text-xs text-muted-foreground mt-0.5 truncate">
                  Opens the exact location in a new tab
                </div>
              </div>
              <ExternalLink className="w-4 h-4 text-pine-500 shrink-0 group-hover:translate-x-0.5 transition-transform" />
            </a>
          </div>
        </div>

        <div>
          <LeadFormPage source="contact_form" kicker="Send a message" title="How can we help?" intro="" />
        </div>
      </div>
    </div>
  );
}
