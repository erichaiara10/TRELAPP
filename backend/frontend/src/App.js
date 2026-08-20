import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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
import MarketEvidence from "@/pages/admin/market/Evidence";
import { AdvertiserWorkspace, ReferralPartnerWorkspace } from "@/pages/account/Workspaces";

function Protected({ children, categories }) {
  const { user } = useAuth();
  if (user === null) return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  if (categories && !categories.includes(user.account_category || "STAFF")) {
    return <Navigate to={user.workspace_path || "/"} replace />;
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
          </Route>

          <Route path="/admin/login" element={<Login />} />
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
            <Route path="market/evidence" element={<MarketEvidence />} />
          </Route>
          <Route path="/advertiser" element={<Protected categories={["PROPERTY_ADVERTISER"]}><AdvertiserWorkspace /></Protected>} />
          <Route path="/referral-partner" element={<Protected categories={["REFERRAL_PARTNER"]}><ReferralPartnerWorkspace /></Protected>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster richColors position="top-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}
