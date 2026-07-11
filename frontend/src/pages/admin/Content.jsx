import React, { useEffect, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";

const SITE_FIELDS = [
  { key: "agency_name", label: "Agency name" },
  { key: "short_name", label: "Short name (e.g. TREL)" },
  { key: "tagline", label: "Tagline" },
  { key: "phone", label: "Phone" },
  { key: "whatsapp", label: "WhatsApp" },
  { key: "email", label: "Email" },
  { key: "address", label: "Address", type: "textarea" },
  { key: "logo_url", label: "Logo URL", type: "image" },
  { key: "favicon_url", label: "Favicon URL", type: "image" },
  { key: "og_image_url", label: "OG / Social share image URL", type: "image" },
  { key: "og_description", label: "OG description (SEO / social preview)", type: "textarea" },
];

function SiteField({ field, value, onChange }) {
  const common = "mt-1 w-full border border-border rounded px-2 py-1.5";
  const testId = `site-${field.key}`;
  if (field.type === "textarea") {
    return (
      <label className="block text-sm md:col-span-2">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">{field.label}</span>
        <textarea rows={3} value={value || ""} onChange={onChange} data-testid={testId} className={common} />
      </label>
    );
  }
  return (
    <label className="block text-sm">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{field.label}</span>
      <input value={value || ""} onChange={onChange} data-testid={testId} className={common} />
      {field.type === "image" && value && (
        <img src={value} alt={field.label} className="mt-2 h-12 w-auto object-contain border border-border rounded p-1 bg-white" data-testid={`${testId}-preview`} />
      )}
    </label>
  );
}

export default function Content() {
  const [site, setSite] = useState({});
  const [about, setAbout] = useState({});
  useEffect(() => {
    api.get("/content/site").then((r) => setSite(r.data?.value || {}));
    api.get("/content/about").then((r) => setAbout(r.data?.value || {}));
  }, []);
  const save = async (key, val) => {
    try { await api.put(`/content/${key}`, val); toast.success("Saved"); }
    catch (e) { toast.error(formatError(e)); }
  };
  const setSiteField = (k) => (e) => setSite({ ...site, [k]: e.target.value });

  return (
    <div>
      <h1 className="text-2xl font-semibold">Website content</h1>
      <p className="text-sm text-muted-foreground">Edit brand assets, contact details, and page copy. Changes go live immediately.</p>
      <div className="mt-4 grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-lg border border-border p-4">
          <div className="font-medium mb-3">Site details</div>
          <div className="grid md:grid-cols-2 gap-3">
            {SITE_FIELDS.map((f) => (
              <SiteField key={f.key} field={f} value={site[f.key]} onChange={setSiteField(f.key)} />
            ))}
          </div>
          <button onClick={() => save("site", site)} data-testid="site-save" className="mt-4 px-3 py-2 rounded-md bg-[#0F172A] text-white">Save site details</button>
        </div>
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="font-medium mb-3">About page</div>
          <label className="block text-sm">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Heading</span>
            <input value={about.heading || ""} onChange={(e) => setAbout({ ...about, heading: e.target.value })} data-testid="about-heading" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
          <label className="block text-sm mt-2">
            <span className="text-xs uppercase tracking-widest text-muted-foreground">Body</span>
            <textarea rows={8} value={about.body || ""} onChange={(e) => setAbout({ ...about, body: e.target.value })} data-testid="about-body" className="mt-1 w-full border border-border rounded px-2 py-1.5" />
          </label>
          <button onClick={() => save("about", about)} data-testid="about-save" className="mt-4 px-3 py-2 rounded-md bg-[#0F172A] text-white">Save about page</button>
        </div>
      </div>
      <div className="mt-3 text-xs text-muted-foreground">
        Tip: paste any public image URL (Unsplash, your CDN, etc.) into the Logo / Favicon / OG image fields — a preview appears below the input.
      </div>
    </div>
  );
}
