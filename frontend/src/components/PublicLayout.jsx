import React, { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { api } from "@/lib/api";
import PublicHeader from "@/components/public/PublicHeader";
import PublicFooter from "@/components/public/PublicFooter";

const DEFAULT_SITE = {
  agency_name: "PNG Realty",
  tagline: "Homes rooted in the heart of Papua New Guinea",
  phone: "+675 7100 0000",
  whatsapp: "6757100000",
  email: "hello@pngrealty.pg",
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
      <PublicHeader site={site} />
      <main className="flex-1"><Outlet /></main>
      <PublicFooter site={site} />
    </div>
  );
}
