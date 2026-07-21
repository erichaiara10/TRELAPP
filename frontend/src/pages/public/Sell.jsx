import React, { useState } from "react";
import { usePage } from "@/lib/usePage";
import LeadFormPage, { RequiredMark } from "./LeadFormPage";
import PhotoUploader from "@/components/PhotoUploader";
import MapCoordsField from "@/components/MapCoordsField";
import LocationPicker from "@/components/LocationPicker";
import AIPriceAnalysis from "@/components/AIPriceAnalysis";
import {
  BadgeCheck, Camera, Megaphone, Headphones,
  ShieldCheck, Users, Wallet, Wrench, Building2, HomeIcon,
  Star, Award, Clock, MapPin,
} from "lucide-react";

const BRAND_BLUE = "#0d50e0";

// Curated lucide icons available for Sell benefits (admin can type any of these
// names into the Content editor's icon field).
const ICONS = {
  BadgeCheck, Camera, Megaphone, Headphones,
  ShieldCheck, Users, Wallet, Wrench, Building2, HomeIcon,
  Star, Award, Clock, MapPin,
};

function BenefitIcon({ name, className = "w-6 h-6" }) {
  const Cmp = ICONS[name] || BadgeCheck;
  return <Cmp className={className} strokeWidth={1.75} aria-hidden="true" />;
}

export default function Sell() {
  const { sections } = usePage("sell");
  const hero = sections.hero || {};
  const benefits = sections.benefits || [];
  const [prop, setProp] = useState({ property_type: "house", price: "", province: "", location: "", suburb: "", bedrooms: "", map_coords: "" });
  const [photos, setPhotos] = useState([]);

  const extra = (
    <>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Property type<RequiredMark /></span>
        <select value={prop.property_type} onChange={(e) => setProp({ ...prop, property_type: e.target.value })} data-testid="sell_form-type" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="house">House</option><option value="apartment">Apartment</option>
          <option value="townhouse">Townhouse</option><option value="land">Land</option><option value="commercial">Commercial</option>
        </select>
      </label>
      <label className="block md:col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Expected price (PGK)<RequiredMark /></span>
        <div className="mt-1 flex flex-col sm:flex-row sm:items-start gap-2">
          <input type="number" placeholder="e.g. 850000" value={prop.price} onChange={(e) => setProp({ ...prop, price: e.target.value })} data-testid="sell_form-price" className="w-full sm:flex-1 border border-border rounded-lg px-3 py-2.5 bg-white" />
          <div className="w-full sm:w-auto">
            <AIPriceAnalysis
              property_type={prop.property_type}
              listing_type="sale"
              price={prop.price}
              province={prop.province}
              city={prop.location}
              suburb={prop.suburb}
              testIdPrefix="sell-ai-price"
            />
          </div>
        </div>
      </label>
      <LocationPicker
        value={{ province: prop.province, city: prop.location, suburb: prop.suburb }}
        onChange={(v) => setProp({ ...prop, province: v.province, location: v.city, suburb: v.suburb })}
        testIdPrefix="sell_form-location"
      />
      <MapCoordsField
        label="Google Maps location (optional)"
        value={prop.map_coords}
        onChange={(v) => setProp({ ...prop, map_coords: v })}
        testId="sell_form-map-coords"
        city={prop.location}
        suburb={prop.suburb}
        province={prop.province}
      />
      <PhotoUploader value={photos} onChange={setPhotos} testId="sell_form-photos" />
    </>
  );

  const extraRequired = () =>
    Boolean(prop.property_type && String(prop.price).trim() && prop.province && prop.location);

  // Smoothly scroll to the LeadFormPage form when "Request a Valuation" is clicked.
  const scrollToForm = () => {
    const el = document.querySelector("[data-testid=sell_form-form]");
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div>
      <LeadFormPage
        source="sell_form"
        kicker={hero.kicker || "SELL WITH TREL"}
        title={hero.heading || "List your property"}
        intro={hero.intro || ""}
        heroImage={hero.image}
        extra={extra}
        extraPayload={() => ({ ...prop, photos })}
        extraRequired={extraRequired}
      />

      {benefits.length > 0 && (
        <section className="pb-20" data-testid="sell-benefits">
          <div className="container-tight max-w-5xl">
            <div className="text-center">
              <div
                className="text-xs uppercase tracking-[0.3em] font-semibold"
                style={{ color: BRAND_BLUE }}
                data-testid="sell-benefits-kicker"
              >
                Why Sell With TREL
              </div>
              <h2
                className="font-serif text-3xl sm:text-4xl mt-3"
                style={{ color: BRAND_BLUE }}
                data-testid="sell-benefits-heading"
              >
                What you get when you list with us
              </h2>
              <p className="text-ink-700 mt-3 max-w-2xl mx-auto text-sm">
                A dedicated team, professional marketing, and a paid valuation service — everything you need to sell with confidence.
              </p>
            </div>

            <ul
              className="mt-10 grid sm:grid-cols-2 lg:grid-cols-4 gap-4"
              data-testid="sell-benefits-list"
            >
              {benefits.map((b, i) => (
                <li
                  key={i}
                  className="group relative rounded-2xl bg-white border border-border p-6 hover:border-transparent hover:shadow-lg transition-all"
                  data-testid={`sell-benefit-${i}`}
                >
                  <div
                    className="w-11 h-11 rounded-xl grid place-items-center mb-4"
                    style={{ backgroundColor: `${BRAND_BLUE}15`, color: BRAND_BLUE }}
                    data-testid={`sell-benefit-${i}-icon`}
                  >
                    <BenefitIcon name={b.icon} className="w-5 h-5" />
                  </div>
                  <div className="font-serif text-lg leading-tight text-ink-900" data-testid={`sell-benefit-${i}-title`}>
                    {b.title}
                  </div>
                  <p className="text-sm text-ink-700 mt-2 whitespace-pre-line" data-testid={`sell-benefit-${i}-body`}>
                    {b.body}
                  </p>
                </li>
              ))}
            </ul>

            {/* Request a Valuation CTA */}
            <div className="mt-12 text-center" data-testid="sell-valuation-cta">
              <button
                type="button"
                onClick={scrollToForm}
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-full text-white font-medium shadow-md hover:shadow-xl hover:-translate-y-0.5 transition-all"
                style={{ backgroundColor: BRAND_BLUE }}
                data-testid="sell-valuation-btn"
              >
                Request a Valuation
              </button>
              <p className="text-xs text-muted-foreground mt-3" data-testid="sell-valuation-subtext">
                Get your property valuation within 2–3 days.
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
