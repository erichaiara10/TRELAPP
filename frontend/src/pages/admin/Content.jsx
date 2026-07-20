import React, { useEffect, useMemo, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Save } from "lucide-react";
import ImageField from "@/components/admin/ImageField";
import MapCoordsField from "@/components/MapCoordsField";

// ---------------- Page schemas --------------------------------------------
// Each entry describes editable sections. Types: "text" | "textarea" | "image"
// or "list" (rendered with add/remove) or "group" (nested fields).
const PAGE_SCHEMAS = [
  {
    key: "branding", label: "Branding & Site",
    endpoint: "content", contentKey: "site",
    fields: [
      { key: "agency_name", label: "Agency name" },
      { key: "short_name", label: "Short name (e.g. TREL)" },
      { key: "tagline", label: "Tagline" },
      { key: "phone", label: "Phone" },
      { key: "whatsapp", label: "WhatsApp" },
      { key: "email", label: "Email" },
      { key: "address", label: "Address", type: "textarea" },
      { key: "map_coords", label: "Office Google Maps coordinates", type: "mapcoords" },
      { key: "logo_url", label: "Logo URL", type: "image" },
      { key: "favicon_url", label: "Favicon URL", type: "image" },
      { key: "og_image_url", label: "OG / social share image", type: "image" },
      { key: "og_description", label: "OG description (SEO / social preview)", type: "textarea" },
    ],
  },
  {
    key: "home", label: "Home page", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker (small tagline)" },
        { key: "heading", label: "Main heading" },
        { key: "sub", label: "Sub-heading", type: "textarea" },
        { key: "cta_primary.label", label: "Primary CTA label" },
        { key: "cta_primary.href", label: "Primary CTA link" },
        { key: "cta_secondary.label", label: "Secondary CTA label" },
        { key: "cta_secondary.href", label: "Secondary CTA link" },
      ]},
      { key: "featured_intro", label: "Featured section intro", type: "group", fields: [
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "sub", label: "Sub-text", type: "textarea" },
      ]},
      { key: "why_us", label: "Why choose us", type: "group", fields: [
        { key: "heading", label: "Heading" },
      ]},
      { key: "why_us.items", label: "Why-us items", type: "list", itemFields: [
        { key: "title", label: "Title" },
        { key: "body", label: "Body", type: "textarea" },
        { key: "icon", label: "Icon name (lucide, e.g. MapPin, ShieldCheck, Briefcase)" },
      ]},
      { key: "wanted_preview", label: "Wanted teaser", type: "group", fields: [
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "sub", label: "Sub-text", type: "textarea" },
      ]},
      { key: "cta_band", label: "Bottom CTA band", type: "group", fields: [
        { key: "heading", label: "Heading" },
        { key: "sub", label: "Sub-text", type: "textarea" },
        { key: "button_label", label: "Button label" },
      ]},
    ],
  },
  {
    key: "about", label: "About page", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
      { key: "story", label: "Our story", type: "group", fields: [
        { key: "heading", label: "Heading" },
        { key: "body", label: "Body", type: "textarea" },
      ]},
      { key: "mission", label: "Mission", type: "group", fields: [
        { key: "heading", label: "Heading" },
        { key: "body", label: "Body", type: "textarea" },
      ]},
      { key: "vision", label: "Vision", type: "group", fields: [
        { key: "heading", label: "Heading" },
        { key: "body", label: "Body", type: "textarea" },
      ]},
      { key: "values", label: "Core values", type: "list", itemFields: [
        { key: "title", label: "Title" },
        { key: "body", label: "Body", type: "textarea" },
      ]},
      { key: "team", label: "Team members", type: "list", itemFields: [
        { key: "name", label: "Name" },
        { key: "role", label: "Role" },
        { key: "photo", label: "Photo", type: "image" },
        { key: "bio", label: "Bio", type: "textarea" },
      ]},
    ],
  },
  {
    key: "sell", label: "Sell page", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
      { key: "benefits", label: "Benefits", type: "list", itemFields: [
        { key: "title", label: "Title" },
        { key: "body", label: "Body", type: "textarea" },
        { key: "icon", label: "Icon name (lucide, e.g. BadgeCheck, Camera, Megaphone, Headphones)" },
      ]},
    ],
  },
  {
    key: "buy", label: "Buy page", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
    ],
  },
  {
    key: "rent", label: "Rent page", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
    ],
  },
  {
    key: "wanted", label: "Property Wanted", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
    ],
  },
  {
    key: "management", label: "Property Management", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
      { key: "services", label: "Services", type: "list", itemFields: [
        { key: "title", label: "Title" },
        { key: "body", label: "Body", type: "textarea" },
        { key: "icon", label: "Icon name (lucide, e.g. Users, Wallet, Wrench)" },
      ]},
    ],
  },
  {
    key: "corporate", label: "Corporate Services", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "image", label: "Hero image", type: "image" },
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
      { key: "services", label: "Services", type: "list", itemFields: [
        { key: "title", label: "Title" },
        { key: "body", label: "Body", type: "textarea" },
        { key: "icon", label: "Icon name (lucide, e.g. Plane, Building2, BarChart3)" },
      ]},
    ],
  },
  {
    key: "contact", label: "Contact page", endpoint: "page",
    sections: [
      { key: "hero", label: "Hero", type: "group", fields: [
        { key: "kicker", label: "Kicker" },
        { key: "heading", label: "Heading" },
        { key: "intro", label: "Intro", type: "textarea" },
      ]},
      { key: "business_hours", label: "Business hours (single field)", type: "flat" },
      { key: "map_coords", label: "Office Google Maps location (overrides branding coords)", type: "flat-mapcoords" },
    ],
  },
  {
    key: "legal_privacy", label: "Privacy Policy", endpoint: "page",
    sections: [
      { key: "title", label: "Title", type: "flat" },
      { key: "body", label: "Body", type: "flat-textarea" },
    ],
  },
  {
    key: "legal_terms", label: "Terms of Service", endpoint: "page",
    sections: [
      { key: "title", label: "Title", type: "flat" },
      { key: "body", label: "Body", type: "flat-textarea" },
    ],
  },
];

// ---------------- helpers -------------------------------------------------
function getPath(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}
function setPath(obj, path, value) {
  const keys = path.split(".");
  const out = { ...(obj || {}) };
  let cur = out;
  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i];
    cur[k] = { ...(cur[k] || {}) };
    cur = cur[k];
  }
  cur[keys[keys.length - 1]] = value;
  return out;
}

// ---------------- generic field renderer ----------------------------------
function TextInput({ field, value, onChange, testId }) {
  const cls = "mt-1 w-full border border-border rounded px-2 py-1.5 text-sm";
  if (field.type === "textarea") {
    return (
      <label className="block">
        <span className="text-xs uppercase tracking-widest text-muted-foreground">{field.label}</span>
        <textarea rows={4} value={value ?? ""} onChange={(e) => onChange(e.target.value)} data-testid={testId} className={cls} />
      </label>
    );
  }
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-widest text-muted-foreground">{field.label}</span>
      <input value={value ?? ""} onChange={(e) => onChange(e.target.value)} data-testid={testId} className={cls} />
    </label>
  );
}

// ---------------- Page editor ---------------------------------------------
function BrandingEditor({ schema, onSaved }) {
  const [state, setState] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setLoading(true);
    api.get(`/content/${schema.contentKey}`)
      .then((r) => setState(r.data?.value || {}))
      .finally(() => setLoading(false));
  }, [schema.contentKey]);

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/content/${schema.contentKey}`, state);
      toast.success("Saved. Live site refreshed.");
      onSaved?.();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;
  return (
    <div className="grid md:grid-cols-2 gap-4">
      {schema.fields.map((f) => {
        if (f.type === "image") {
          return <div key={f.key} className="md:col-span-2"><ImageField label={f.label} value={state[f.key] || ""} onChange={(v) => setState({ ...state, [f.key]: v })} testId={`branding-${f.key}`} /></div>;
        }
        if (f.type === "mapcoords") {
          return <div key={f.key} className="md:col-span-2"><MapCoordsField label={f.label} value={state[f.key] || ""} onChange={(v) => setState({ ...state, [f.key]: v })} testId={`branding-${f.key}`} /></div>;
        }
        return (
          <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
            <TextInput field={f} value={state[f.key]} onChange={(v) => setState({ ...state, [f.key]: v })} testId={`branding-${f.key}`} />
          </div>
        );
      })}
      <div className="md:col-span-2 pt-2">
        <button onClick={save} disabled={saving} data-testid="branding-save" className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-pine-500 hover:bg-pine-600 text-white disabled:opacity-60">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save changes
        </button>
      </div>
    </div>
  );
}

function ListEditor({ page, section, itemFields, items = [], onReload }) {
  const [saving, setSaving] = useState(false);

  const addItem = async () => {
    setSaving(true);
    try {
      const blank = {};
      itemFields.forEach((f) => (blank[f.key] = ""));
      await api.post(`/page/${page}/list/${section}`, blank);
      onReload?.();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  const deleteItem = async (idx) => {
    setSaving(true);
    try {
      await api.delete(`/page/${page}/list/${section}/${idx}`);
      onReload?.();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-3">
      {items.map((it, idx) => (
        <div key={idx} className="rounded-lg border border-border bg-sand-50/60 p-3" data-testid={`list-${section}-item-${idx}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">#{idx + 1}</div>
            <button type="button" onClick={() => deleteItem(idx)} disabled={saving} data-testid={`list-${section}-delete-${idx}`}
              className="inline-flex items-center gap-1 text-xs text-destructive hover:underline">
              <Trash2 className="w-3.5 h-3.5" /> Remove
            </button>
          </div>
          <ItemFields fields={itemFields} value={it} onChange={(patch) => {
            // update in memory & bubble up: parent updates 'state'
            const evt = new CustomEvent("list-item-update", { detail: { section, idx, patch } });
            window.dispatchEvent(evt);
          }} testIdPrefix={`list-${section}-${idx}`} />
        </div>
      ))}
      <button onClick={addItem} disabled={saving} data-testid={`list-${section}-add`}
        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-dashed border-border text-sm hover:bg-white">
        <Plus className="w-3.5 h-3.5" /> Add item
      </button>
    </div>
  );
}

function ItemFields({ fields, value = {}, onChange, testIdPrefix = "item" }) {
  return (
    <div className="grid md:grid-cols-2 gap-3">
      {fields.map((f) => (
        f.type === "image" ? (
          <div key={f.key} className="md:col-span-2">
            <ImageField label={f.label} value={value[f.key] || ""} onChange={(v) => onChange({ [f.key]: v })} testId={`${testIdPrefix}-${f.key}`} />
          </div>
        ) : (
          <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
            <TextInput field={f} value={value[f.key]} onChange={(v) => onChange({ [f.key]: v })} testId={`${testIdPrefix}-${f.key}`} />
          </div>
        )
      ))}
    </div>
  );
}

function PageEditor({ schema }) {
  const [state, setState] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const reload = () => {
    setLoading(true);
    api.get(`/page/${schema.key}`).then((r) => setState(r.data?.sections || {})).finally(() => setLoading(false));
  };
  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [schema.key]);

  // Listen for inline list-item mutations
  useEffect(() => {
    const handler = (e) => {
      const { section, idx, patch } = e.detail || {};
      setState((prev) => {
        const list = Array.isArray(prev[section]) ? [...prev[section]] : [];
        list[idx] = { ...(list[idx] || {}), ...patch };
        return { ...prev, [section]: list };
      });
    };
    window.addEventListener("list-item-update", handler);
    return () => window.removeEventListener("list-item-update", handler);
  }, []);

  const updateField = (path, value) => setState((prev) => setPath(prev, path, value));

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/page/${schema.key}`, { sections: state });
      toast.success("Saved. Live site refreshed.");
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>;

  return (
    <div className="space-y-5">
      {schema.sections.map((sec) => {
        if (sec.type === "flat") {
          return (
            <div key={sec.key}>
              <TextInput field={{ label: sec.label }} value={state[sec.key]} onChange={(v) => setState({ ...state, [sec.key]: v })} testId={`field-${sec.key}`} />
            </div>
          );
        }
        if (sec.type === "flat-textarea") {
          return (
            <div key={sec.key}>
              <TextInput field={{ label: sec.label, type: "textarea" }} value={state[sec.key]} onChange={(v) => setState({ ...state, [sec.key]: v })} testId={`field-${sec.key}`} />
            </div>
          );
        }
        if (sec.type === "flat-mapcoords") {
          return (
            <div key={sec.key}>
              <MapCoordsField label={sec.label} value={state[sec.key] || ""} onChange={(v) => setState({ ...state, [sec.key]: v })} testId={`field-${sec.key}`} />
            </div>
          );
        }
        if (sec.type === "group") {
          const [primary] = sec.key.split(".");
          return (
            <section key={sec.key} className="rounded-xl border border-border bg-white p-4">
              <h3 className="text-sm font-semibold mb-3">{sec.label}</h3>
              <div className="grid md:grid-cols-2 gap-3">
                {sec.fields.map((f) => {
                  const fullPath = `${primary}.${f.key}`;
                  const v = getPath(state, fullPath);
                  if (f.type === "image") {
                    return <div key={f.key} className="md:col-span-2"><ImageField label={f.label} value={v || ""} onChange={(val) => updateField(fullPath, val)} testId={`field-${fullPath}`} /></div>;
                  }
                  return (
                    <div key={f.key} className={f.type === "textarea" ? "md:col-span-2" : ""}>
                      <TextInput field={f} value={v} onChange={(val) => updateField(fullPath, val)} testId={`field-${fullPath}`} />
                    </div>
                  );
                })}
              </div>
            </section>
          );
        }
        if (sec.type === "list") {
          const items = getPath(state, sec.key) || [];
          return (
            <section key={sec.key} className="rounded-xl border border-border bg-white p-4">
              <h3 className="text-sm font-semibold mb-3">{sec.label}</h3>
              <ListEditor page={schema.key} section={sec.key} itemFields={sec.itemFields} items={items} onReload={reload} />
            </section>
          );
        }
        return null;
      })}
      <div className="sticky bottom-0 bg-gradient-to-t from-sand-50 to-transparent pt-3 pb-1 -mx-1">
        <button onClick={save} disabled={saving} data-testid="page-save"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-pine-500 hover:bg-pine-600 text-white disabled:opacity-60 shadow-md">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save changes
        </button>
      </div>
    </div>
  );
}

// ---------------- main --------------------------------------------------------
export default function Content() {
  const [activeKey, setActiveKey] = useState(PAGE_SCHEMAS[0].key);
  const active = useMemo(() => PAGE_SCHEMAS.find((s) => s.key === activeKey), [activeKey]);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Website content</h1>
      <p className="text-sm text-muted-foreground">Pick a page from the sidebar and edit hero, copy, images, team members, services and more. Changes save to the database and go live immediately.</p>

      <div className="mt-5 grid lg:grid-cols-[220px_1fr] gap-6">
        <aside className="border border-border rounded-xl bg-white p-2 h-fit sticky top-4" data-testid="content-page-list">
          <div className="text-[11px] uppercase tracking-widest text-muted-foreground px-2 pt-1.5 pb-1">Pages</div>
          <nav className="flex flex-col gap-0.5">
            {PAGE_SCHEMAS.map((s) => (
              <button key={s.key} onClick={() => setActiveKey(s.key)}
                data-testid={`content-tab-${s.key}`}
                className={`text-left px-3 py-2 rounded-md text-sm ${activeKey === s.key ? "bg-pine-500 text-white" : "hover:bg-sand-100"}`}>
                {s.label}
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">{active.label}</h2>
            <span className="text-xs text-muted-foreground">Live at <code className="text-ink-900">/{active.key === "home" ? "" : active.key.replace("legal_", "")}</code></span>
          </div>
          {active.endpoint === "content"
            ? <BrandingEditor schema={active} />
            : <PageEditor schema={active} />}
        </div>
      </div>
    </div>
  );
}
