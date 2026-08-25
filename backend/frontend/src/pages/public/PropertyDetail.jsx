import React, { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, money, formatError } from "@/lib/api";
import { Bed, Bath, Car, MapPin, Phone, MessageCircle, ShieldCheck, Calendar, CheckCircle2, ExternalLink, Info } from "lucide-react";
import { toast } from "sonner";
import HumanVerification from "@/components/HumanVerification";
import { mapsUrlFromCoords } from "@/components/MapCoordsField";
import PriceCompareButton from "@/components/PriceCompareButton";
import NearbyAmenities from "@/components/NearbyAmenities";
import NameInput from "@/components/NameInput";
import PhoneInput from "@/components/PhoneInput";

export default function PropertyDetail() {
  const { id } = useParams();
  const [p, setP] = useState(null);
  const [site, setSite] = useState({ phone: "+675 76281552", whatsapp: "+675 8138 3302" });
  const [imgIdx, setImgIdx] = useState(0);
  const [form, setForm] = useState({ customer_name: "", customer_phone: "", customer_email: "", preferred_date: "" });
  const [contact, setContact] = useState({ name: "", email: "", phone: "", message: "" });
  const [contactSent, setContactSent] = useState(false);
  const [inspectionSent, setInspectionSent] = useState(false);
  const [locationForm, setLocationForm] = useState({ requester_name: "", requester_email: "", requester_phone: "", reason: "Property enquiry", message: "" });
  const [locationSent, setLocationSent] = useState("");
  const inspectionCaptchaRef = useRef(null);
  const contactCaptchaRef = useRef(null);
  const locationCaptchaRef = useRef(null);

  useEffect(() => {
    api.get(`/properties/${id}`).then((r) => setP(r.data)).catch(() => setP(false));
    api.get("/content/site").then((r) => r.data?.value && setSite((s) => ({ ...s, ...r.data.value })));
  }, [id]);

  useEffect(() => {
    if (p && window.location.hash === "#price-guidance") {
      requestAnimationFrame(() => document.getElementById("price-guidance")?.scrollIntoView({ block: "center" }));
    }
  }, [p]);

  if (p === null) return <div className="container-tight py-10 text-muted-foreground">Loading…</div>;
  if (p === false) return <div className="container-tight py-10">Property not found. <Link to="/buy" className="text-pine-500 underline">Back to search</Link></div>;

  const requestInspection = async (e) => {
    e.preventDefault();
    if (!inspectionCaptchaRef.current?.isValid()) { toast.error("Please complete the human verification"); return; }
    try {
      await api.post("/public/inspections", { property_id: p.id, ...form, ...inspectionCaptchaRef.current.getPayload() });
      setInspectionSent(true);
    } catch (e) { toast.error(formatError(e)); inspectionCaptchaRef.current?.refresh(); }
  };

  const submitEnquiry = async (e) => {
    e.preventDefault();
    if (!contactCaptchaRef.current?.isValid()) { toast.error("Please complete the human verification"); return; }
    try {
      await api.post("/public/leads", { source: "contact_form", ...contact, property_id: p.id, ...contactCaptchaRef.current.getPayload() });
      setContactSent(true);
    } catch (e) { toast.error(formatError(e)); contactCaptchaRef.current?.refresh(); }
  };

  const requestExactLocation = async (e) => {
    e.preventDefault();
    if (!locationCaptchaRef.current?.isValid()) { toast.error("Please complete the human verification"); return; }
    try {
      const { data } = await api.post("/property-advertising/location-requests", { property_id: p.id, ...locationForm, ...locationCaptchaRef.current.getPayload() });
      setLocationSent(data.reference);
    } catch (e) { toast.error(formatError(e)); locationCaptchaRef.current?.refresh(); }
  };

  const wa = (site.whatsapp || "").replace(/\D/g, "");
  const waLink = `https://wa.me/${wa}?text=${encodeURIComponent(`Hi TREL, I'm interested in "${p.title}" (${window.location.href})`)}`;
  // Show precise Google Maps link only when the property has parseable coords.
  const mapLink = mapsUrlFromCoords(p.map_coords);

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
          <div className="flex items-center gap-3 text-sm text-muted-foreground mt-2 flex-wrap">
            <span className="flex items-center gap-1"><MapPin className="w-4 h-4" /> {p.suburb ? `${p.suburb}, ` : ""}{p.location}</span>
            {mapLink ? (
              <a
                href={mapLink}
                target="_blank"
                rel="noreferrer"
                data-testid="detail-map-btn"
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full border border-pine-500 text-pine-500 hover:bg-pine-500 hover:text-white transition-colors text-xs font-medium"
              >
                View on Google Maps <ExternalLink className="w-3 h-3" />
              </a>
            ) : (
              <span
                role="note"
                data-testid="detail-map-empty"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-dashed border-border text-[11px] text-muted-foreground"
              >
                <Info className="w-3 h-3" />
                Google location not registered for this property
              </span>
            )}
          </div>
          <div id="price-guidance" className="mt-4 flex flex-col sm:flex-row sm:items-center gap-3 flex-wrap scroll-mt-24">
            <div className="text-3xl font-semibold text-pine-500">
              {p.price_label||money(p.price, p.currency || "PGK")}{p.listing_type === "rent"&&(!p.price_type||p.price_type==="PGK") && <span className="text-base text-muted-foreground"> / month</span>}
            </div>
            {(!p.price_type||p.price_type==="PGK")&&<PriceCompareButton
              property={p}
              audience="buyer"
              testIdPrefix="detail-ai-price"
            />}
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
          {(p.allotment_number || p.section_number || p.full_portion_number || p.total_area_ha || p.street_name || p.nearby_landmark) && (
            <div className="mt-6" data-testid="detail-legal-block">
              <h2 className="font-serif text-2xl mb-3">Legal &amp; location details</h2>
              <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                {(p.allotment_number || p.section_number) && (
                  <>
                    <div><dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Lot</dt><dd className="text-ink-900">{p.allotment_number || "—"}</dd></div>
                    <div><dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Section</dt><dd className="text-ink-900">{p.section_number || "—"}</dd></div>
                  </>
                )}
                {p.full_portion_number && (
                  <div className="sm:col-span-2"><dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Portion number</dt><dd className="text-ink-900">{p.full_portion_number}</dd></div>
                )}
                {p.total_area_ha ? (
                  <div><dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Total area</dt><dd className="text-ink-900">{Number(p.total_area_ha).toLocaleString(undefined, { maximumFractionDigits: 4 })} ha</dd></div>
                ) : null}
                {p.street_name && (
                  <div><dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Street</dt><dd className="text-ink-900">{p.street_name}</dd></div>
                )}
                {p.nearby_landmark && (
                  <div className="sm:col-span-2"><dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Nearby landmark</dt><dd className="text-ink-900">{p.nearby_landmark}</dd></div>
                )}
              </dl>
            </div>
          )}
          <NearbyAmenities
            suburb={p.suburb}
            city={p.location}
            province={p.province}
            property_type={p.property_type}
            testId="detail-nearby-amenities"
          />
        </div>

        {/* Sidebar */}
        <aside className="space-y-4">
          <form onSubmit={requestExactLocation} className="bg-white rounded-2xl border border-border p-6" data-testid="exact-location-form">
            <h3 className="font-serif text-xl flex items-center gap-2"><MapPin className="w-5 h-5" />Request exact location</h3>
            <p className="text-xs text-muted-foreground mt-2">The exact residential location is protected and is shared only after the authorised decision.</p>
            {locationSent ? <div className="mt-4 rounded-lg bg-pine-500 text-white p-4"><CheckCircle2 className="w-5 h-5"/><p>Request received. Reference: <b>{locationSent}</b></p></div> : <div className="mt-4 space-y-2">
              <NameInput value={locationForm.requester_name} onChange={v=>setLocationForm({...locationForm,requester_name:v})} testId="location-name" placeholder="Your name"/>
              <input required type="email" placeholder="Email" value={locationForm.requester_email} onChange={e=>setLocationForm({...locationForm,requester_email:e.target.value})} className="w-full border border-border rounded-lg px-3 py-2"/>
              <PhoneInput value={locationForm.requester_phone} onChange={v=>setLocationForm({...locationForm,requester_phone:v})} testId="location-phone"/>
              <select value={locationForm.reason} onChange={e=>setLocationForm({...locationForm,reason:e.target.value})} className="w-full border border-border rounded-lg px-3 py-2"><option>Property enquiry</option><option>Inspection planning</option><option>Due diligence</option></select>
              <textarea placeholder="Why do you need the exact location?" rows={3} value={locationForm.message} onChange={e=>setLocationForm({...locationForm,message:e.target.value})} className="w-full border border-border rounded-lg px-3 py-2"/>
              <HumanVerification ref={locationCaptchaRef}/>
              <button className="w-full py-2.5 rounded-full bg-ink-900 hover:bg-ink-700 text-white">Submit location request</button>
            </div>}
          </form>
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
              {contactSent ? (
                <div className="rounded-lg bg-pine-500 text-white p-4" data-testid="detail-contact-success">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-medium">Thank you!</div>
                      <p className="text-xs text-sand-100 mt-1">Your enquiry was received. An agent will attend to you shortly.</p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <NameInput value={contact.name} onChange={(v) => setContact({ ...contact, name: v })} testId="contact-name" placeholder="Your name" />
                  <input required type="email" placeholder="Email" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} data-testid="contact-email" className="w-full border border-border rounded-lg px-3 py-2" />
                  <PhoneInput value={contact.phone} onChange={(v) => setContact({ ...contact, phone: v })} testId="contact-phone" />
                  <textarea placeholder="Message" rows={3} value={contact.message} onChange={(e) => setContact({ ...contact, message: e.target.value })} data-testid="contact-msg" className="w-full border border-border rounded-lg px-3 py-2" />
                  <HumanVerification ref={contactCaptchaRef} />
                  <button className="w-full py-2.5 rounded-full bg-ink-900 hover:bg-ink-700 text-white" data-testid="contact-submit">Send enquiry</button>
                </>
              )}
            </form>
          </div>

          <form onSubmit={requestInspection} className="bg-pine-500 text-white rounded-2xl p-6" data-testid="inspection-form">
            <h3 className="font-serif text-xl flex items-center gap-2"><Calendar className="w-5 h-5" />Request inspection</h3>
            {inspectionSent ? (
              <div className="mt-4 rounded-lg bg-white/15 border border-white/25 p-4" data-testid="inspection-success">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium">Inspection requested!</div>
                    <p className="text-xs text-sand-100 mt-1">An agent will confirm your preferred time shortly.</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-4 space-y-2">
                <NameInput value={form.customer_name} onChange={(v) => setForm({ ...form, customer_name: v })} testId="insp-name" placeholder="Your name" />
                <PhoneInput value={form.customer_phone} onChange={(v) => setForm({ ...form, customer_phone: v })} testId="insp-phone" />
                <input type="email" placeholder="Email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} data-testid="insp-email" className="w-full rounded-lg px-3 py-2 text-ink-900" />
                <input type="date" value={form.preferred_date} onChange={(e) => setForm({ ...form, preferred_date: e.target.value })} data-testid="insp-date" className="w-full rounded-lg px-3 py-2 text-ink-900" />
                <HumanVerification ref={inspectionCaptchaRef} />
                <button className="w-full py-2.5 rounded-full bg-white text-pine-500 font-medium hover:bg-sand-50" data-testid="insp-submit">Request inspection</button>
              </div>
            )}
          </form>
        </aside>
      </div>
    </div>
  );
}
