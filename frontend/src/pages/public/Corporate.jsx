import React, { useState } from "react";
import { usePage } from "@/lib/usePage";
import LeadFormPage from "./LeadFormPage";

export default function Corporate() {
  const { sections } = usePage("corporate");
  const hero = sections.hero || {};
  const services = sections.services || [];
  const [d, setD] = useState({ company: "", intent: "rent", property_type: "apartment", min_price: "", max_price: "", staff_count: "" });
  const extra = (
    <>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Company</span>
        <input value={d.company} onChange={(e) => setD({ ...d, company: e.target.value })} data-testid="corporate_form-company" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" placeholder="Your company / organisation" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Requirement</span>
        <select value={d.intent} onChange={(e) => setD({ ...d, intent: e.target.value })} data-testid="corporate_form-intent" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="rent">Corporate rental</option><option value="buy">Purchase</option><option value="either">Either</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Property type</span>
        <select value={d.property_type} onChange={(e) => setD({ ...d, property_type: e.target.value })} data-testid="corporate_form-type" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white">
          <option value="apartment">Apartment</option><option value="house">House</option><option value="townhouse">Townhouse</option><option value="commercial">Commercial</option>
        </select>
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Number of staff / units</span>
        <input type="number" value={d.staff_count} onChange={(e) => setD({ ...d, staff_count: e.target.value })} data-testid="corporate_form-staff" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" placeholder="e.g. 12" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Budget min (PGK)</span>
        <input type="number" value={d.min_price} onChange={(e) => setD({ ...d, min_price: e.target.value })} data-testid="corporate_form-min" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" placeholder="Minimum monthly / total budget" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Budget max (PGK)</span>
        <input type="number" value={d.max_price} onChange={(e) => setD({ ...d, max_price: e.target.value })} data-testid="corporate_form-max" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" placeholder="Maximum monthly / total budget" />
      </label>
    </>
  );

  return (
    <div>
      <LeadFormPage
        source="corporate_form"
        kicker={hero.kicker || "CORPORATE SERVICES"}
        title={hero.heading || "Corporate real estate solutions"}
        intro={hero.intro || ""}
        heroImage={hero.image}
        extra={extra}
        extraPayload={() => ({ ...d, min_price: Number(d.min_price) || 0, max_price: Number(d.max_price) || 0 })}
      />
      {services.length > 0 && (
        <section className="container-tight pb-16 max-w-4xl" data-testid="corporate-services">
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Corporate desk</div>
          <h2 className="font-serif text-3xl mt-2">Services we provide</h2>
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            {services.map((s, i) => (
              <div key={i} className="bg-white rounded-2xl p-5 border border-border" data-testid={`corporate-service-${i}`}>
                <div className="font-serif text-xl">{s.title}</div>
                <p className="text-sm text-ink-700 mt-2 whitespace-pre-line">{s.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
