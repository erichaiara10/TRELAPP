import React, { useEffect, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";

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
  return (
    <div>
      <h1 className="text-2xl font-semibold">Website content</h1>
      <div className="mt-4 grid md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="font-medium mb-2">Site details</div>
          {["agency_name","tagline","phone","whatsapp","email","address"].map((k) => (
            <label key={k} className="block mt-2 text-sm"><span className="text-xs uppercase tracking-widest text-muted-foreground">{k}</span>
              <input value={site[k] || ""} onChange={(e) => setSite({ ...site, [k]: e.target.value })} data-testid={`site-${k}`} className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
          ))}
          <button onClick={() => save("site", site)} data-testid="site-save" className="mt-3 px-3 py-2 rounded-md bg-[#0F172A] text-white">Save</button>
        </div>
        <div className="bg-white rounded-lg border border-border p-4">
          <div className="font-medium mb-2">About page</div>
          <label className="block text-sm"><span className="text-xs uppercase tracking-widest text-muted-foreground">Heading</span>
            <input value={about.heading || ""} onChange={(e) => setAbout({ ...about, heading: e.target.value })} data-testid="about-heading" className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
          <label className="block text-sm mt-2"><span className="text-xs uppercase tracking-widest text-muted-foreground">Body</span>
            <textarea rows={6} value={about.body || ""} onChange={(e) => setAbout({ ...about, body: e.target.value })} data-testid="about-body" className="mt-1 w-full border border-border rounded px-2 py-1.5" /></label>
          <button onClick={() => save("about", about)} data-testid="about-save" className="mt-3 px-3 py-2 rounded-md bg-[#0F172A] text-white">Save</button>
        </div>
      </div>
    </div>
  );
}
