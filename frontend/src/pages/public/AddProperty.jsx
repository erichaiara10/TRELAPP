import React, { useCallback, useMemo, useState } from "react";
import { Check, Home, KeyRound, UserRound } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import AccountAccessDialog from "@/components/public/AccountAccessDialog";

const serviceOptions = {
  sell: [
    { id: "sell-managed", title: "I want TREL to sell my property", text: "TREL will assist you through the sale process." },
    { id: "sell-advertise", title: "I want TREL to advertise my property on this website — I will handle the sale", text: "Publish the property and manage the sale yourself." },
  ],
  rent: [
    { id: "rent-managed", title: "I want TREL to find a tenant and manage my property", text: "TREL will find the tenant and manage the property for you." },
    { id: "rent-advertise", title: "I want TREL to advertise my property on this website — I will manage the rental", text: "Publish the property and manage the rental yourself." },
  ],
};

const relationships = [
  { id: "owner", label: "I am the owner or joint owner" },
  { id: "agent", label: "I am an authorised real estate agent" },
  { id: "representative", label: "I am authorised to act for the owner" },
];

function StepNumber({ children }) {
  return <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[#0398FC] text-sm font-bold text-black">{children}</span>;
}

function RadioMark({ selected }) {
  return <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border ${selected ? "border-[#0398FC]" : "border-slate-400"}`}>{selected && <span className="h-3 w-3 rounded-full bg-[#0398FC]" />}</span>;
}

export default function AddProperty() {
  const [params, setParams] = useSearchParams();
  const [purpose, setPurpose] = useState(params.get("purpose") || "sell");
  const [service, setService] = useState(params.get("service") || "sell-managed");
  const [relationship, setRelationship] = useState(params.get("relationship") || "owner");
  const auth = params.get("auth");
  const currentServices = serviceOptions[purpose];
  const selectedService = useMemo(() => currentServices.find((item) => item.id === service)?.title, [currentServices, service]);

  const choosePurpose = (nextPurpose) => {
    setPurpose(nextPurpose);
    setService(serviceOptions[nextPurpose][0].id);
  };
  const openDialog = (tab) => setParams({ purpose, service, relationship, auth: tab });
  const closeDialog = useCallback(() => {
    const next = new URLSearchParams(params);
    next.delete("auth");
    setParams(next, { replace: true });
  }, [params, setParams]);

  return (
    <main className="min-h-[calc(100vh-4rem)] bg-slate-50 px-4 py-8 sm:py-12" data-testid="add-property-options-page">
      <section className="mx-auto max-w-5xl rounded-2xl border border-slate-200 bg-white px-6 py-7 shadow-sm sm:px-12 sm:py-9">
        <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">Add Your Property</h1>
        <p className="mt-2 text-sm text-slate-600">Tell us what you would like to do. It only takes a moment.</p>

        <div className="mt-7 flex items-center gap-3"><StepNumber>1</StepNumber><h2 className="text-sm font-semibold text-slate-900">What would you like to do?</h2></div>
        <div className="ml-10 mt-3 grid gap-4 sm:grid-cols-2">
          {[{ id: "sell", label: "Sell", icon: Home }, { id: "rent", label: "Rent", icon: KeyRound }].map((item) => {
            const Icon = item.icon;
            const selected = purpose === item.id;
            return <button key={item.id} type="button" onClick={() => choosePurpose(item.id)} className={`flex h-20 items-center gap-5 rounded-md border px-5 text-left transition ${selected ? "border-[#0398FC] bg-sky-50/60" : "border-slate-300 bg-white"}`}>
              <Icon className={`h-8 w-8 ${selected ? "text-[#0398FC]" : "text-slate-500"}`} /><span className="text-xl font-semibold text-slate-950">{item.label}</span><span className="ml-auto">{selected ? <span className="grid h-6 w-6 place-items-center rounded-full bg-[#0398FC]"><Check className="h-4 w-4 text-black" /></span> : <span className="block h-6 w-6 rounded-full border border-slate-400" />}</span>
            </button>;
          })}
        </div>

        <div className="mt-6 flex items-center gap-3"><StepNumber>2</StepNumber><h2 className="text-sm font-semibold text-slate-900">How would you like TREL to help?</h2></div>
        <div className="ml-10 mt-3 space-y-3">
          {currentServices.map((item) => {
            const selected = service === item.id;
            return <button key={item.id} type="button" onClick={() => setService(item.id)} className={`flex w-full items-start gap-4 rounded-md border px-5 py-4 text-left ${selected ? "border-[#0398FC] bg-sky-50/60" : "border-slate-300 bg-white"}`}><RadioMark selected={selected} /><span><span className="block text-sm font-medium text-slate-950">{item.title}</span><span className="mt-1 block text-xs text-slate-500">{item.text}</span></span></button>;
          })}
        </div>

        <div className="mt-6 flex items-center gap-3"><StepNumber>3</StepNumber><h2 className="text-sm font-semibold text-slate-900">What is your relationship to the property?</h2></div>
        <div className="ml-10 mt-3 grid gap-3 md:grid-cols-3">
          {relationships.map((item) => {
            const selected = relationship === item.id;
            return <button key={item.id} type="button" onClick={() => setRelationship(item.id)} className={`flex min-h-14 items-center gap-3 rounded-md border px-4 text-left text-xs ${selected ? "border-[#0398FC] bg-sky-50/60" : "border-slate-300 bg-white"}`}><RadioMark selected={selected} /><span>{item.label}</span></button>;
          })}
        </div>

        <div className="ml-10 mt-6 flex gap-4 rounded-md border border-sky-200 bg-sky-50/60 px-5 py-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-sky-200 bg-white"><UserRound className="h-5 w-5 text-[#0398FC]" /></span><div><h3 className="text-sm font-semibold text-slate-950">Create an account to continue</h3><p className="mt-1 text-xs text-slate-600">Your personal advertising workspace lets you complete your listing and track its progress.</p><p className="mt-1 text-xs text-slate-500">Your selections will be saved.</p></div></div>

        <div className="mx-auto mt-5 grid max-w-xl gap-3 sm:grid-cols-2"><button type="button" onClick={() => openDialog("register")} className="rounded-md bg-[#0398FC] px-5 py-3 text-sm font-semibold text-black">Create My Account</button><button type="button" onClick={() => openDialog("login")} className="rounded-md border border-[#0398FC] bg-white px-5 py-3 text-sm font-semibold text-slate-900">Log In</button></div>
        <p className="mt-4 text-center text-xs text-slate-500">Already registered? <button type="button" onClick={() => openDialog("login")} className="font-semibold text-sky-600">Log in</button> and continue where you stopped.</p>
      </section>
      <AccountAccessDialog open={auth === "login" || auth === "register"} initialTab={auth === "register" ? "register" : "login"} selectedService={selectedService} onClose={closeDialog} />
    </main>
  );
}
