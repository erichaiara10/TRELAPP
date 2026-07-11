import React, { useState } from "react";
import LeadFormPage from "./LeadFormPage";

export default function Corporate() {
  const [d, setD] = useState({ company: "", intent: "rent", property_type: "apartment", min_price: "", max_price: "", staff_count: "" });
  const extra = (
    <>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Company</span>
        <input value={d.company} onChange={(e) => setD({ ...d, company: e.target.value })} data-testid="corporate_form-company" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
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
        <input type="number" value={d.staff_count} onChange={(e) => setD({ ...d, staff_count: e.target.value })} data-testid="corporate_form-staff" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Budget min</span>
        <input type="number" value={d.min_price} onChange={(e) => setD({ ...d, min_price: e.target.value })} data-testid="corporate_form-min" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Budget max</span>
        <input type="number" value={d.max_price} onChange={(e) => setD({ ...d, max_price: e.target.value })} data-testid="corporate_form-max" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5 bg-white" />
      </label>
    </>
  );
  return <LeadFormPage source="corporate_form" kicker="Corporate services"
    title="Corporate real estate solutions"
    intro="Whether you need expat housing, office space or portfolio management, our corporate desk will build a tailored programme for your business."
    extra={extra}
    extraPayload={() => ({ ...d, min_price: Number(d.min_price) || 0, max_price: Number(d.max_price) || 0 })} />;
}
