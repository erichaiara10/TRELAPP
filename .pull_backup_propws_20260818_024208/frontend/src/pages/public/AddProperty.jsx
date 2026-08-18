import React, { useCallback, useMemo, useState } from "react";
import { Building2, CheckCircle2, Home, KeyRound, Megaphone } from "lucide-react";
import { useLocation, useSearchParams } from "react-router-dom";
import AccountAccessDialog from "@/components/public/AccountAccessDialog";

const BLUE = "#0398FC";

const choices = [
  { id: "sell-managed", group: "Sell", icon: Building2, title: "TREL manages the complete sale", text: "TREL handles the selling process from listing through to completion." },
  { id: "sell-advertise", group: "Sell", icon: Megaphone, title: "Advertise only — I will sell the property myself", text: "Publish your property on TRELPNG and manage the sale yourself." },
  { id: "rent-managed", group: "Rent", icon: KeyRound, title: "TREL finds the tenant and manages the property", text: "TREL markets the property, finds the tenant and provides ongoing management." },
  { id: "rent-advertise", group: "Rent", icon: Home, title: "Advertise only — I will manage it myself", text: "Publish your rental property and manage the tenant and property yourself." },
];

export default function AddProperty() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [selected, setSelected] = useState(params.get("service") || "");
  const auth = params.get("auth");
  const selectedChoice = useMemo(() => choices.find((choice) => choice.id === selected), [selected]);

  const closeDialog = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete("auth");
    setParams(next, { replace: true });
  }, [params, setParams]);

  const choose = (choice) => {
    setSelected(choice.id);
    setParams({ service: choice.id, auth: "login" });
  };

  return (
    <main className="bg-slate-50 py-12 sm:py-16" data-testid="add-property-options-page">
      <div className="container-tight">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-sky-600">Add Property</p>
          <h1 className="mt-3 text-3xl font-bold text-slate-900 sm:text-4xl">What would you like to do?</h1>
          <p className="mx-auto mt-3 max-w-2xl text-slate-600">Choose how you want TREL to help you. All options are free in Version 1.</p>
        </div>

        {location.state?.previewNotice && (
          <div className="mx-auto mt-6 flex max-w-3xl items-center gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-slate-700">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-sky-600" /> This is the visual screen preview. Account connection will be added after screen approval.
          </div>
        )}

        {["Sell", "Rent"].map((group) => (
          <section key={group} className="mt-10" aria-labelledby={`${group.toLowerCase()}-heading`}>
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-sky-100 font-bold text-sky-700">{group === "Sell" ? "1" : "2"}</span><h2 id={`${group.toLowerCase()}-heading`} className="text-2xl font-bold text-slate-900">{group} a property</h2></div>
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              {choices.filter((choice) => choice.group === group).map((choice) => {
                const Icon = choice.icon;
                return (
                  <article key={choice.id} className="flex min-h-[260px] flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="grid h-12 w-12 place-items-center rounded-xl bg-sky-100 text-sky-700"><Icon className="h-6 w-6" /></div>
                    <h3 className="mt-5 text-xl font-bold leading-snug text-slate-900">{choice.title}</h3>
                    <p className="mt-3 flex-1 text-sm leading-6 text-slate-600">{choice.text}</p>
                    <button type="button" onClick={() => choose(choice)} className="mt-6 w-full rounded-lg px-4 py-3 font-semibold text-black" style={{ backgroundColor: BLUE }} data-testid={`select-${choice.id}`}>Select</button>
                  </article>
                );
              })}
            </div>
          </section>
        ))}

        <p className="mt-10 text-center text-sm text-slate-600">Already have a TRELPNG account? <button type="button" onClick={() => setParams({ auth: "login" })} className="font-semibold text-sky-600">Log in</button></p>
      </div>

      <AccountAccessDialog
        open={auth === "login" || auth === "register"}
        initialTab={auth === "register" ? "register" : "login"}
        selectedService={selectedChoice?.title}
        onClose={closeDialog}
      />
    </main>
  );
}
