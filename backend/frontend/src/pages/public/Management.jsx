import React from "react";
import { usePage } from "@/lib/usePage";
import LeadFormPage from "./LeadFormPage";

export default function Management() {
  const { sections } = usePage("management");
  const hero = sections.hero || {};
  const services = sections.services || [];
  return (
    <div>
      <LeadFormPage
        source="management_form"
        kicker={hero.kicker || "PROPERTY MANAGEMENT"}
        title={hero.heading || "End-to-end management for landlords"}
        intro={hero.intro || ""}
        heroImage={hero.image}
      />
      {services.length > 0 && (
        <section className="container-tight pb-16 max-w-4xl" data-testid="management-services">
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">What we handle</div>
          <h2 className="font-serif text-3xl mt-2">Services we provide</h2>
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            {services.map((s, i) => (
              <div key={i} className="bg-white rounded-2xl p-5 border border-border" data-testid={`management-service-${i}`}>
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
