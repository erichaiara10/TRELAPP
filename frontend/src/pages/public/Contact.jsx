import React, { useEffect, useState } from "react";
import LeadFormPage from "./LeadFormPage";
import { api } from "@/lib/api";
import { Phone, Mail, MapPin, MessageCircle } from "lucide-react";

export default function Contact() {
  const [site, setSite] = useState({ phone: "", email: "", whatsapp: "", address: "" });
  useEffect(() => { api.get("/content/site").then((r) => r.data?.value && setSite(r.data.value)); }, []);
  return (
    <div>
      <div className="container-tight pt-14 grid md:grid-cols-2 gap-10">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Contact</div>
          <h1 className="font-serif text-5xl mt-3">Get in touch</h1>
          <p className="text-ink-700 mt-4">Reach us during business hours (Mon–Fri, 8am–5pm PGT), or leave a message and we'll respond within one business day.</p>
          <div className="mt-8 space-y-3 text-sm">
            <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-pine-500" />{site.phone}</div>
            <div className="flex items-center gap-2"><Mail className="w-4 h-4 text-pine-500" />{site.email}</div>
            <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-pine-500" />{site.address}</div>
            <a href={`https://wa.me/${(site.whatsapp || "").replace(/\D/g, "")}`} target="_blank" rel="noreferrer" className="inline-flex mt-2 items-center gap-2 px-4 py-2 rounded-full bg-terracotta-500 text-white">
              <MessageCircle className="w-4 h-4" /> Chat on WhatsApp
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
