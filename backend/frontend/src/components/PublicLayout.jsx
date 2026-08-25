import React, { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { api } from "@/lib/api";
import PublicHeader from "@/components/public/PublicHeader";
import PublicFooter from "@/components/public/PublicFooter";
import BrandingHead from "@/components/BrandingHead";

const DEFAULT_SITE = {
  agency_name: "Triumph Real Estate Limited",
  short_name: "TREL",
  tagline: "We Care To Share",
  logo_url: "/images/trel-logo.svg",
  phone: "+675 76281552",
  whatsapp: "+675 8138 3302",
  email: "sales101.trel@gmail.com",
  address: "",
};

export default function PublicLayout() {
  const [site, setSite] = useState(DEFAULT_SITE);

  useEffect(() => {
    api.get("/content/site")
      .then((r) => r.data?.value && setSite((s) => ({ ...s, ...r.data.value })))
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-sand-50 text-ink-900">
      <BrandingHead site={site} />
      <PublicHeader site={site} />
      <main className="flex-1"><Outlet /></main>
      <PublicFooter site={site} />
    </div>
  );
}
