import React, { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, Home as HomeIcon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import AccountAccessDialog from "@/components/public/AccountAccessDialog";

const LISTING_OPTIONS = [
  { key: "sale", label: "Sell", description: "List a property for sale on TRELPNG." },
  { key: "rent", label: "Rent", description: "Let a property to a tenant." },
];

const SERVICE_OPTIONS = (mode) => [
  { key: "trel", label: mode === "sale" ? "I want TREL to sell my property" : "I want TREL to rent my property",
    description: "TRELPNG staff handle marketing, enquiries and negotiation for you." },
  { key: "self", label: mode === "sale" ? "I will handle the sale myself" : "I will handle the rental myself",
    description: "You keep control — TRELPNG lists your property to reach buyers/tenants." },
];

const RELATIONSHIP_OPTIONS = [
  { key: "OWNER", label: "Owner", description: "I own the property and can sign on its behalf." },
  { key: "AUTHORISED_AGENT", label: "Authorized Agent", description: "I hold a written authority to act for the owner." },
  { key: "AUTHORISED_REPRESENTATIVE", label: "Representative", description: "I represent the owner (e.g., executor, family member)." },
];

function OptionCard({ item, checked, onSelect, testId }) {
  return <button type="button" onClick={onSelect} data-testid={testId}
    className={`w-full text-left rounded-xl border p-5 transition ${checked ? "border-[#0398FC] bg-sky-50 ring-2 ring-sky-200" : "border-slate-200 hover:border-[#0398FC]"}`}>
    <div className="flex items-start gap-3">
      <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border ${checked ? "border-[#0398FC] bg-[#0398FC] text-white" : "border-slate-300"}`}>
        {checked && <CheckCircle2 className="h-4 w-4" />}
      </span>
      <div>
        <div className="font-semibold text-slate-900">{item.label}</div>
        <div className="text-sm text-slate-600 mt-0.5">{item.description}</div>
      </div>
    </div>
  </button>;
}

export default function AddProperty() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [listingType, setListingType] = useState("sale");
  const [service, setService] = useState("");
  const [relationship, setRelationship] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogTab, setDialogTab] = useState("login");

  // If the visitor arrived with ?auth=… (e.g., legacy redirect), open the popup.
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const auth = params.get("auth");
    if (["login", "register", "verify", "complete", "forgot", "reset"].includes(auth)) {
      setDialogTab(auth);
      setDialogOpen(true);
    }
  }, [location.search]);

  const selectedService = { listing_type: listingType, service, relationship };
  const queryParams = new URLSearchParams(location.search);
  const dialogNext = queryParams.get("auth") ? (queryParams.get("next") || undefined) : "/advertiser";
  const canProceed = Boolean(listingType && service && relationship);

  const openPopup = useCallback((tab) => {
    if (!canProceed) return;
    setDialogTab(tab);
    setDialogOpen(true);
  }, [canProceed]);

  const closePopup = useCallback(() => {
    setDialogOpen(false);
    const params = new URLSearchParams(location.search);
    if (!params.has("auth")) return;
    params.delete("auth");
    params.delete("reason");
    params.delete("token");
    const search = params.toString();
    navigate(`${location.pathname}${search ? `?${search}` : ""}`, { replace: true });
  }, [location.pathname, location.search, navigate]);

  const proceedAuthed = useCallback(() => {
    if (!canProceed) return;
    navigate("/advertiser", { state: { selectedService } });
  }, [canProceed, navigate, selectedService]);

  if (user === null) return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;

  // Authenticated users of ANY category proceed to the intake form once the
  // three steps are answered. No category-mismatch notices.
  const isAuthed = Boolean(user);

  return <main className="min-h-[calc(100vh-4rem)] bg-slate-50 pb-24" data-testid="add-property-page">
    <section className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="text-center">
        <HomeIcon className="mx-auto h-12 w-12 text-[#0398FC]" />
        <h1 className="mt-3 text-3xl font-bold text-slate-900" data-testid="p01-title">Add Your Property</h1>
        <p className="mt-2 text-sm text-slate-600">Answer three quick questions so we can route your listing to the right TRELPNG workflow.</p>
      </header>

      {/* Step 1: Sell or Rent */}
      <div className="mt-10">
        <h2 className="text-lg font-semibold text-slate-900">Step 1 · What would you like to do?</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {LISTING_OPTIONS.map((item) => (
            <OptionCard key={item.key} item={item}
              checked={listingType === item.key}
              onSelect={() => { setListingType(item.key); setService(""); }}
              testId={`p01-listing-${item.key}`} />
          ))}
        </div>
      </div>

      {/* Step 2: TREL vs self */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-slate-900">Step 2 · How would you like to handle it?</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {SERVICE_OPTIONS(listingType).map((item) => (
            <OptionCard key={item.key} item={item}
              checked={service === item.key}
              onSelect={() => setService(item.key)}
              testId={`p01-service-${item.key}`} />
          ))}
        </div>
      </div>

      {/* Step 3: Relationship */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold text-slate-900">Step 3 · Your relationship to the property</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {RELATIONSHIP_OPTIONS.map((item) => (
            <OptionCard key={item.key} item={item}
              checked={relationship === item.key}
              onSelect={() => setRelationship(item.key)}
              testId={`p01-relationship-${item.key.toLowerCase()}`} />
          ))}
        </div>
      </div>
    </section>

    {/* Sticky CTA bar */}
    <div className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white/90 backdrop-blur px-4 py-4 sm:px-6" data-testid="p01-cta-bar">
      <div className="mx-auto max-w-3xl flex flex-col sm:flex-row items-stretch gap-3">
        {isAuthed ? (
          <button type="button" onClick={proceedAuthed} disabled={!canProceed}
            data-testid="p01-proceed-authed"
            className="flex-1 rounded-full bg-[#0398FC] px-6 py-3 text-base font-semibold text-black disabled:opacity-50">
            Continue to property details
          </button>
        ) : (<>
          <button type="button" onClick={() => openPopup("register")} disabled={!canProceed}
            data-testid="p01-create-account"
            className="flex-1 rounded-full bg-[#0398FC] px-6 py-3 text-base font-semibold text-black disabled:opacity-50">
            Create My Account
          </button>
          <button type="button" onClick={() => openPopup("login")} disabled={!canProceed}
            data-testid="p01-login"
            className="flex-1 rounded-full border-2 border-[#0398FC] px-6 py-3 text-base font-semibold text-[#0398FC] disabled:opacity-50">
            Log In
          </button>
        </>)}
      </div>
      {!canProceed && (
        <p className="mt-2 text-center text-xs text-slate-500" data-testid="p01-cta-hint">Answer all three steps above to continue.</p>
      )}
    </div>

    <AccountAccessDialog
      open={dialogOpen}
      initialTab={dialogTab}
      onClose={closePopup}
      selectedService={selectedService}
      next={dialogNext}
      resetToken={queryParams.get("token") || ""}
    />
  </main>;
}
