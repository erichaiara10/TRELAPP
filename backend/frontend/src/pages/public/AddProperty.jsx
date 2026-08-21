import React, { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, LogOut, ArrowRight, Home as HomeIcon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import AccountAccessDialog from "@/components/public/AccountAccessDialog";

// Category-mismatch notice. Never redirects silently — always presents a choice.
function CategoryNotice({ title, message, primaryLabel, primaryTo }) {
  const { logout } = useAuth();
  const nav = useNavigate();
  const primary = useCallback(() => nav(primaryTo, { replace: true }), [nav, primaryTo]);
  const switchAccount = useCallback(async () => {
    await logout();
    nav("/add-property?auth=login&next=/advertiser", { replace: true });
  }, [logout, nav]);
  return <main className="min-h-[calc(100vh-4rem)] bg-slate-50 px-4 py-10 sm:py-14" data-testid="add-property-category-notice">
    <section className="mx-auto max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm">
      <div className="flex items-start gap-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-amber-100"><AlertTriangle className="h-6 w-6 text-amber-600" /></span>
        <div>
          <h1 className="text-xl font-semibold text-slate-950">{title}</h1>
          <p className="mt-2 text-sm text-slate-600">{message}</p>
        </div>
      </div>
      <div className="mt-7 flex flex-col gap-3 sm:flex-row">
        <button type="button" onClick={primary} data-testid="add-property-return-primary" className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#168CF5] px-5 py-3 text-sm font-semibold text-white hover:bg-[#0878D8]">
          {primaryLabel} <ArrowRight className="h-4 w-4" />
        </button>
        <button type="button" onClick={switchAccount} data-testid="add-property-switch-account" className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">
          <LogOut className="h-4 w-4" /> Log Out and Use Another Account
        </button>
      </div>
    </section>
  </main>;
}

export default function AddProperty() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const authParam = params.get("auth");
  const nextParam = params.get("next");
  const intendedNext = nextParam || "/advertiser";
  // The popup opens automatically on arrival and stays open until the visitor
  // dismisses it. Kept in local state so a URL round-trip is not required to
  // control visibility.
  const initialTab = authParam === "register" ? "register" : "login";
  const [dialogOpen, setDialogOpen] = useState(true);
  const [dialogTab, setDialogTab] = useState(initialTab);
  useEffect(() => {
    if (authParam === "register" || authParam === "login") {
      setDialogTab(authParam);
      setDialogOpen(true);
    }
  }, [authParam]);
  const closeDialog = useCallback(() => setDialogOpen(false), []);

  if (user === null) return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;

  if (user) {
    const category = user.account_category;
    if (category === "PROPERTY_ADVERTISER") return <Navigate to={intendedNext} replace />;
    if (category === "STAFF") {
      return <CategoryNotice
        title="Your current account is a Staff Account."
        message="Adding a property requires a Property Advertiser Account. Return to the Staff workspace or log out to use another account."
        primaryLabel="Return to Staff Workspace" primaryTo={user.workspace_path || "/admin"} />;
    }
    if (category === "REFERRAL_PARTNER") {
      return <CategoryNotice
        title="Your current account is a Referral Partner Account."
        message="Use your Referral Partner workspace to submit a property referral, or use a Property Advertiser Account to advertise a property."
        primaryLabel="Go to Referral Partner Workspace" primaryTo="/referral-partner" />;
    }
    return <CategoryNotice
      title="Your current account cannot advertise properties."
      message="Log out and use a Property Advertiser Account, or contact TRELPNG support."
      primaryLabel="Return Home" primaryTo="/" />;
  }

  // Unauthenticated visitor: the approved popup is presented, no property
  // questions are shown before authentication.
  return <main className="min-h-[calc(100vh-4rem)] bg-slate-50 px-4 py-10" data-testid="add-property-authgate">
    <section className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white px-8 py-10 text-center shadow-sm">
      <HomeIcon className="mx-auto h-12 w-12 text-[#0398FC]" />
      <h1 className="mt-3 text-xl font-semibold text-slate-950">Sign in to add your property</h1>
      <p className="mt-2 text-sm text-slate-600">Adding a property requires a Property Advertiser Account. Use the popup to log in or create one now.</p>
      {!dialogOpen && (
        <button type="button" onClick={() => setDialogOpen(true)} data-testid="reopen-popup" className="mt-6 rounded-full bg-[#0398FC] px-6 py-3 text-sm font-semibold text-black">
          Open sign-in popup
        </button>
      )}
    </section>
    <AccountAccessDialog
      open={dialogOpen}
      initialTab={dialogTab}
      onClose={closeDialog}
      next={intendedNext}
    />
  </main>;
}
