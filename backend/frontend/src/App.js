import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Toaster } from "@/components/ui/sonner";

import PublicLayout from "@/components/PublicLayout";
import AdminLayout from "@/components/AdminLayout";

import Home from "@/pages/public/Home";
import Search from "@/pages/public/Search";
import PropertyDetail from "@/pages/public/PropertyDetail";
import Sell from "@/pages/public/Sell";
import Wanted from "@/pages/public/Wanted";
import Management from "@/pages/public/Management";
import Corporate from "@/pages/public/Corporate";
import About from "@/pages/public/About";
import Contact from "@/pages/public/Contact";
import Legal from "@/pages/public/Legal";

import Login from "@/pages/admin/Login";
import Dashboard from "@/pages/admin/Dashboard";
import Properties from "@/pages/admin/Properties";
import Customers from "@/pages/admin/Customers";
import Leads from "@/pages/admin/Leads";
import Requirements from "@/pages/admin/Requirements";
import Matching from "@/pages/admin/Matching";
import Inspections from "@/pages/admin/Inspections";
import Tasks from "@/pages/admin/Tasks";
import Pipeline from "@/pages/admin/Pipeline";
import Users from "@/pages/admin/Users";
import Content from "@/pages/admin/Content";
import Locations from "@/pages/admin/Locations";
import Reports from "@/pages/admin/Reports";
import {
  Overview as PropertyAdvertisingOverview,
  Advertisers as PropertyAdvertisers,
  AdvertiserProfile,
  IdentityVerification,
  Submissions as PropertySubmissions,
  SubmissionOverviewPage,
  PropertyLocationPage,
  PriceFeaturesPage,
  PhotosDocumentsPage,
  PublicContentPage,
  ConflictResolution,
  AuthorityReview,
  PublicationQueue,
  PublicationReview,
  LifecycleQueue,
  LifecycleReview,
} from "@/pages/admin/property-advertising/StaffPropertyAdvertising";
import MarketEvidence from "@/pages/admin/market/Evidence";
import { ReferralPartnerWorkspace } from "@/pages/account/Workspaces";
import AdvertiserWorkspace from "@/pages/advertiser/AdvertiserWorkspace";
import Register from "@/pages/account/Register";
import AddProperty from "@/pages/public/AddProperty";
import { workspaceForUser } from "@/lib/accountRouting";

function Protected({ children, categories }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === null) return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    if (categories?.includes("STAFF")) {
      return <Navigate to={`/login?next=${next}`} replace />;
    }
    return <Navigate to={`/add-property?auth=login&next=${next}`} replace />;
  }
  if (categories && !categories.includes(user.account_category)) {
    return <Navigate to={workspaceForUser(user)} replace />;
  }
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<Home />} />
            <Route path="/buy" element={<Search mode="sale" />} />
            <Route path="/rent" element={<Search mode="rent" />} />
            <Route path="/property/:id" element={<PropertyDetail />} />
            <Route path="/sell" element={<Sell />} />
            <Route path="/wanted" element={<Wanted />} />
            <Route path="/management" element={<Management />} />
            <Route path="/corporate" element={<Corporate />} />
            <Route path="/about" element={<About />} />
            <Route path="/contact" element={<Contact />} />
            <Route path="/privacy" element={<Legal kind="privacy" />} />
            <Route path="/terms" element={<Legal kind="terms" />} />
            <Route path="/add-property" element={<AddProperty />} />
          </Route>

          <Route path="/login" element={<Login />} />
          <Route path="/admin/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/admin" element={<Protected categories={["STAFF"]}><AdminLayout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="properties" element={<Properties />} />
            <Route path="customers" element={<Customers />} />
            <Route path="leads" element={<Leads />} />
            <Route path="requirements" element={<Requirements />} />
            <Route path="matching" element={<Matching />} />
            <Route path="inspections" element={<Inspections />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="pipeline" element={<Pipeline />} />
            <Route path="users" element={<Users />} />
            <Route path="locations" element={<Locations />} />
            <Route path="content" element={<Content />} />
            <Route path="reports" element={<Reports />} />
            <Route path="property-advertising" element={<PropertyAdvertisingOverview />} />
            <Route path="property-advertising/advertisers" element={<PropertyAdvertisers />} />
            <Route path="property-advertising/advertisers/:advertiserId" element={<AdvertiserProfile />} />
            <Route path="property-advertising/advertisers/:advertiserId/identity" element={<IdentityVerification />} />
            <Route path="property-advertising/submissions" element={<PropertySubmissions />} />
            <Route path="property-advertising/submissions/:submissionRef" element={<SubmissionOverviewPage />} />
            <Route path="property-advertising/submissions/:submissionRef/property-location" element={<PropertyLocationPage />} />
            <Route path="property-advertising/submissions/:submissionRef/price-features" element={<PriceFeaturesPage />} />
            <Route path="property-advertising/submissions/:submissionRef/photos-documents" element={<PhotosDocumentsPage />} />
            <Route path="property-advertising/submissions/:submissionRef/public-content" element={<PublicContentPage />} />
            <Route path="property-advertising/conflicts/:submissionRef" element={<ConflictResolution />} />
            <Route path="property-advertising/authority/:submissionRef" element={<AuthorityReview />} />
            <Route path="property-advertising/publications" element={<PublicationQueue />} />
            <Route path="property-advertising/publications/:listingRef" element={<PublicationReview />} />
            <Route path="property-advertising/lifecycle" element={<LifecycleQueue />} />
            <Route path="property-advertising/lifecycle/:listingRef" element={<LifecycleReview />} />
            <Route path="market/evidence" element={<MarketEvidence />} />
          </Route>
          <Route path="/advertiser/*" element={<Protected categories={["PROPERTY_ADVERTISER"]}><AdvertiserWorkspace /></Protected>} />
          <Route path="/referral-partner" element={<Protected categories={["REFERRAL_PARTNER"]}><ReferralPartnerWorkspace /></Protected>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster richColors position="top-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}
