import React, { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, money, formatError } from "@/lib/api";
import { Bed, Bath, Car, MapPin, Phone, MessageCircle, ShieldCheck, Calendar } from "lucide-react";
import { toast } from "sonner";
import HumanVerification from "@/components/HumanVerification";

export default function PropertyDetail() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [site, setSite] = useState({ phone: "+675 76281552", whatsapp: "+675 8138 3302" });
  const [imgIdx, setImgIdx] = useState(0);
  const [form, setForm] = useState({ customer_name: "", customer_phone: "", customer_email: "", preferred_date: "" });
  const [contact, setContact] = useState({ name: "", email: "", phone: "", message: "" });
  const inspectionCaptchaRef = useRef(null);
  const contactCaptchaRef = useRef(null);

  useEffect(() => {
    api.get(`/properties/${id}`).then((r) => setP(r.data)).catch(() => setP(false));
    api.get("/content/site").then((r) => r.data?.value && setSite((s) => ({ ...s, ...r.data.value })));
  }, [id]);

  if (p === null) return <div className="container-tight py-10 text-muted-foreground">Loading…</div>;
  if (p === false) return <div className="container-tight py-10">Property not found. <Link to="/buy" className="text-pine-500 underline">Back to search</Link></div>;

  const requestInspection = async (e) => {
    e.preventDefault();
    if (!inspectionCaptchaRef.current?.isValid()) { toast.error("Please complete the human verification"); return; }
    try {
      await api.post("/public/inspections", { property_id: p.id, ...form, ...inspectionCaptchaRef.current.getPayload() });
      toast.success("Inspection request sent! Our agent will contact you shortly.");
      setForm({ customer_name: "", customer_phone: "", customer_email: "", preferred_date: "" });
      inspectionCaptchaRef.current?.refresh();
    } catch (e) { toast.error(formatError(e)); inspectionCaptchaRef.current?.refresh(); }
  };

  const submitEnquiry = async (e) => {
    e.preventDefault();
    if (!contactCaptchaRef.current?.isValid()) { toast.error("Please complete the human verification"); return; }
    try {
      await api.post("/public/leads", { source: "contact_form", ...contact, property_id: p.id, ...contactCaptchaRef.current.getPayload() });
      toast.success("Enquiry sent! We'll be in touch soon.");
      setContact({ name: "", email: "", phone: "", message: "" });
      contactCaptchaRef.current?.refresh();
    } catch (e) { toast.error(formatError(e)); contactCaptchaRef.current?.refresh(); }
  };

  const wa = (site.whatsapp || "").replace(/\D/g, "");
  const waLink = `https://wa.me/${wa}?text=${encodeURIComponent(`Hi TREL, I'm interested in "${p.title}" (${window.location.href})`)}`;

  return (
    <div className="container-tight py-8">
      {/* Gallery */}
      <div className="grid md:grid-cols-3 gap-2 rounded-2xl overflow-hidden">
        <div className="md:col-span-2 aspect-[16/10] bg-sand-100 overflow-hidden">
          <img src={p.images?.[imgIdx] || p.images?.[0]} alt={p.title} className="w-full h-full object-cover" data-testid="detail-hero-img" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-1 gap-2">
          {p.images?.slice(0, 4).map((src, i) => (
            <button key={i} onClick={() => setImgIdx(i)} data-testid={`thumb-${i}`}
              className={`aspect-video overflow-hidden rounded-lg ${imgIdx===i?"ring-2 ring-pine-500":""}`}>
              <img src={src} alt="" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="px-2 py-1 rounded-full bg-sand-100 capitalize">{p.property_type}</span>
            <span className="px-2 py-1 rounded-full bg-pine-500 text-white capitalize">
              {p.listing_type === "sale" ? "For sale" : "For rent"}
            </span>
            {p.verified && <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-terracotta-50 text-terracotta-600"><ShieldCheck className="w-3 h-3" />Verified</span>}
          </div>
          <h1 className="font-serif text-4xl mt-3">{p.title}</h1>
          <div className="flex items-center gap-1 text-sm text-muted-foreground mt-2">
            <MapPin className="w-4 h-4" /> {p.suburb ? `${p.suburb}, ` : ""}{p.location}
          </div>
          <div className="mt-4 text-3xl font-semibold text-pine-500">
            {money(p.price, p.currency || "PGK")}{p.listing_type === "rent" && <span className="text-base text-muted-foreground"> / month</span>}
          </div>
          <div className="mt-6 flex flex-wrap gap-6 text-sm text-ink-700 border-y border-border py-4">
            {p.bedrooms > 0 && <span className="flex items-center gap-2"><Bed className="w-4 h-4" /><b>{p.bedrooms}</b> bedrooms</span>}
            {p.bathrooms > 0 && <span className="flex items-center gap-2"><Bath className="w-4 h-4" /><b>{p.bathrooms}</b> bathrooms</span>}
            {p.parking > 0 && <span className="flex items-center gap-2"><Car className="w-4 h-4" /><b>{p.parking}</b> parking</span>}
            {p.area_sqm && <span><b>{p.area_sqm}</b> sqm</span>}
          </div>
          <div className="mt-6">
            <h2 className="font-serif text-2xl mb-2">Description</h2>
            <p className="text-ink-700 leading-relaxed whitespace-pre-line">{p.description}</p>
          </div>
          {p.features?.length > 0 && (
            <div className="mt-6">
              <h2 className="font-serif text-2xl mb-3">Features</h2>
              <div className="flex flex-wrap gap-2">
                {p.features.map((f) => <span key={f} className="px-3 py-1.5 rounded-full bg-sand-100 text-sm">{f}</span>)}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <aside className="space-y-4">
          <div className="bg-white rounded-2xl border border-border p-6">
            <h3 className="font-serif text-xl">Contact agent</h3>
            <div className="mt-4 flex flex-col gap-2">
              <a href={`tel:${site.phone}`} className="px-4 py-2.5 rounded-full bg-pine-500 hover:bg-pine-600 text-white text-center flex items-center justify-center gap-2" data-testid="detail-call-btn">
                <Phone className="w-4 h-4" /> Call {site.phone}
              </a>
              <a href={waLink} target="_blank" rel="noreferrer" className="px-4 py-2.5 rounded-full bg-terracotta-500 hover:bg-terracotta-600 text-white text-center flex items-center justify-center gap-2" data-testid="detail-whatsapp-btn">
                <MessageCircle className="w-4 h-4" /> WhatsApp
              </a>
            </div>
            <form onSubmit={submitEnquiry} className="mt-6 space-y-2" data-testid="detail-contact-form">
              <input required placeholder="Your name" value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} data-testid="contact-name" className="w-full border border-border rounded-lg px-3 py-2" />
              <input required type="email" placeholder="Email" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} data-testid="contact-email" className="w-full border border-border rounded-lg px-3 py-2" />
              <input placeholder="Phone" value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} data-testid="contact-phone" className="w-full border border-border rounded-lg px-3 py-2" />
              <textarea placeholder="Message" rows={3} value={contact.message} onChange={(e) => setContact({ ...contact, message: e.target.value })} data-testid="contact-msg" className="w-full border border-border rounded-lg px-3 py-2" />
              <HumanVerification ref={contactCaptchaRef} />
              <button className="w-full py-2.5 rounded-full bg-ink-900 hover:bg-ink-700 text-white" data-testid="contact-submit">Send enquiry</button>
            </form>
          </div>

          <form onSubmit={requestInspection} className="bg-pine-500 text-white rounded-2xl p-6" data-testid="inspection-form">
            <h3 className="font-serif text-xl flex items-center gap-2"><Calendar className="w-5 h-5" />Request inspection</h3>
            <div className="mt-4 space-y-2">
              <input required placeholder="Your name" value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} data-testid="insp-name" className="w-full rounded-lg px-3 py-2 text-ink-900" />
              <input placeholder="Phone" value={form.customer_phone} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} data-testid="insp-phone" className="w-full rounded-lg px-3 py-2 text-ink-900" />
              <input type="email" placeholder="Email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} data-testid="insp-email" className="w-full rounded-lg px-3 py-2 text-ink-900" />
              <input type="date" value={form.preferred_date} onChange={(e) => setForm({ ...form, preferred_date: e.target.value })} data-testid="insp-date" className="w-full rounded-lg px-3 py-2 text-ink-900" />
              <HumanVerification ref={inspectionCaptchaRef} />
              <button className="w-full py-2.5 rounded-full bg-white text-pine-500 font-medium hover:bg-sand-50" data-testid="insp-submit">Request inspection</button>
            </div>
          </form>
        </aside>
      </div>
    </div>
  );
}
