// SourceModal — the redesigned "Add / Edit Source" popup.
// See the BRS: source name + base URL + description on the LEFT, live
// "Discover Pages" results on the RIGHT, collector/frequency/parser on the
// bottom row, and a "What happens next?" reassurance card. The scraper uses
// the EXACT confirmed URLs from listing_pages — no reconstruction anywhere.
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2, ChevronRight, ExternalLink, Globe, Info, Key, Save, X,
} from "lucide-react";

import { api, formatError } from "@/lib/api";

const emptyForm = {
  name: "", base_url: "", description: "",
  allow_source_auto_match: true, active: true,
  collector: "generic_web",
  collection_frequency: "daily",
  parser_version: "1.0",
  listing_pages: [],
};

// Map category keys to a small icon so the discovery table has visual anchor
// points that match the screenshot.
const CATEGORY_ICON = {
  buy_for_sale: Globe,
  buy:          Globe,
  rent:         Key,
  residential:  Globe,
  commercial:   Globe,
  land:         Globe,
  projects:     Globe,
  apartments:   Globe,
  houses:       Globe,
};

export default function SourceModal({ editing, initial, collectors, onClose, onSaved }) {
  const [form, setForm] = useState(() => ({ ...emptyForm, ...(initial || {}) }));
  const [discovering, setDiscovering] = useState(false);
  const [discovery, setDiscovery] = useState(null);           // full backend response
  const [confirmed, setConfirmed] = useState({});             // {listing_url: bool}
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Pre-seed confirmed state from either discovery results or the
    // existing source's persisted listing_pages.
    if (initial?.listing_pages?.length) {
      const c = {};
      initial.listing_pages.forEach((p) => { c[p.listing_url] = p.auto_confirm !== false && !p.covered_by; });
      setConfirmed(c);
    }
  }, [initial]);

  const canDiscover = !!form.base_url;

  const runDiscovery = async () => {
    if (!canDiscover) {
      toast.error("Enter a website base URL first");
      return;
    }
    setDiscovering(true); setDiscovery(null);
    try {
      const { data } = await api.post(
        `/admin/market/collectors/${form.collector}/discover`,
        { base_url: form.base_url, parser_config: form.parser_config || {} },
      );
      setDiscovery(data);
      if (!data.ok) {
        toast.error(data.error || "Discovery failed");
        return;
      }
      // Prime the confirm checkboxes off the auto_confirm flag
      const c = {};
      (data.candidates || []).forEach((p) => {
        if (p.auto_confirm) c[p.listing_url] = true;
      });
      setConfirmed(c);
      toast.success(
        `${data.candidates?.length ?? 0} candidate${data.candidates?.length === 1 ? "" : "s"} found · ` +
        `${Object.keys(c).length} auto-confirmed`
      );
    } catch (e) { toast.error(formatError(e)); }
    finally { setDiscovering(false); }
  };

  const toggleConfirm = (url) =>
    setConfirmed((c) => ({ ...c, [url]: !c[url] }));

  const save = async () => {
    if (!form.name?.trim()) { toast.error("Source name is required"); return; }
    // Only send the confirmed candidates — the scraper uses these EXACT urls
    const candidates = discovery?.candidates || (initial?.listing_pages || []).map((p) => ({
      ...p, listing_url: p.listing_url,
    }));
    const confirmed_pages = candidates
      .filter((c) => confirmed[c.listing_url])
      .map((c) => ({
        category:       c.category,
        category_label: c.category_label,
        purpose:        c.purpose,
        listing_url:    c.listing_url,
        cards_found:    c.cards_found,
        detail_links:   c.detail_links,
        priced_cards:   c.priced_cards,
        unpriced_cards: c.unpriced_cards,
        canonical:      c.canonical !== false,
        auto_confirm:   true,
        covered_by:     c.covered_by || null,
        confidence:     c.confidence,
        extraction_strategy: c.extraction_strategy,
        profile_version: c.profile_version || "2.0",
        selection_reason: c.selection_reason,
      }));

    setSaving(true);
    try {
      const learned = candidates.find((c) => confirmed[c.listing_url] && c.learned_card_selector);
      const parser_config = learned ? {
        ...(form.parser_config || {}),
        card: learned.learned_card_selector,
        source_profile: {
          version: learned.profile_version || "2.0",
          strategy: learned.extraction_strategy || "adaptive_dom",
          confidence: learned.confidence || 0,
          validated_at: new Date().toISOString(),
        },
      } : (form.parser_config || {});
      const payload = { ...form, parser_version: "2.0", parser_config, listing_pages: confirmed_pages };
      if (editing === "new") await api.post("/admin/market/sources", payload);
      else await api.put(`/admin/market/sources/${editing}`, payload);
      toast.success(`Saved — ${confirmed_pages.length} confirmed listing page${confirmed_pages.length === 1 ? "" : "s"}`);
      onSaved?.();
    } catch (e) { toast.error(formatError(e)); }
    finally { setSaving(false); }
  };

  const discovered = discovery?.candidates || (initial?.listing_pages || []).map((p) => ({
    ...p, accessible: true, status: 200,
    auto_confirm: p.auto_confirm !== false && !p.covered_by,
  }));

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-4 overflow-y-auto"
         onClick={onClose} data-testid="source-modal">
      <div className="bg-white rounded-lg w-full max-w-6xl my-6" onClick={(e) => e.stopPropagation()}>
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <div className="text-2xl font-semibold" data-testid="source-modal-title">
                {editing === "new" ? "Add Source" : "Edit Source"}
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                Add a new property data source and confirm its listing pages.
              </div>
            </div>
            <button onClick={onClose} className="text-muted-foreground hover:text-foreground"
                    data-testid="close-source-modal">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body — 2-column grid: form (left, 5) + discovery table (right, 7) */}
          <div className="grid lg:grid-cols-12 gap-6">
            {/* LEFT */}
            <div className="lg:col-span-5 space-y-4">
              <FieldWithLabel label="Source Name" required testid="src-name">
                <input value={form.name}
                       onChange={(e) => setForm({ ...form, name: e.target.value })}
                       placeholder="e.g. Hausples PNG"
                       className="w-full border border-border rounded px-3 py-2 text-sm"
                       data-testid="input-source-name" />
              </FieldWithLabel>

              <FieldWithLabel label="Base URL" required testid="src-baseurl"
                              hint="Enter the website homepage. We will discover listing pages automatically.">
                <div className="flex gap-2">
                  <input value={form.base_url}
                         onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                         placeholder="https://www.example.com/"
                         className="flex-1 border border-border rounded px-3 py-2 text-sm"
                         data-testid="input-source-baseurl" />
                  <button onClick={runDiscovery} disabled={!canDiscover || discovering}
                          className="whitespace-nowrap px-3 py-2 text-sm rounded border border-[#2A5B46] text-[#2A5B46] hover:bg-[#F1F6F3] disabled:opacity-50 flex items-center gap-1.5"
                          data-testid="discover-pages-btn">
                    <Globe className="w-4 h-4" />
                    {discovering ? "Scanning…" : "Discover Pages"}
                  </button>
                </div>
              </FieldWithLabel>

              <FieldWithLabel label="Description" testid="src-desc">
                <textarea value={form.description || ""}
                          rows={4} maxLength={200}
                          onChange={(e) => setForm({ ...form, description: e.target.value })}
                          className="w-full border border-border rounded px-3 py-2 text-sm resize-none"
                          data-testid="input-source-desc" />
                <div className="text-[10px] text-muted-foreground text-right mt-1">
                  {(form.description || "").length}/200
                </div>
              </FieldWithLabel>
            </div>

            {/* RIGHT */}
            <div className="lg:col-span-7">
              <DiscoveryPanel
                discovering={discovering}
                discovery={discovery}
                discovered={discovered}
                confirmed={confirmed}
                onToggle={toggleConfirm}
                onRun={runDiscovery}
                canDiscover={canDiscover}
                initial={initial}
              />
            </div>
          </div>

          {/* Second row: toggles + collector settings + reassurance */}
          <div className="grid lg:grid-cols-12 gap-6 mt-6">
            <div className="lg:col-span-3 space-y-3">
              <ToggleRow label="Active" hint="Enable this source for collection"
                         checked={!!form.active} testid="src-active"
                         onChange={(v) => setForm({ ...form, active: v })} />
              <ToggleRow label="Allow auto-match" hint="Allow automatic duplicate matching"
                         checked={!!form.allow_source_auto_match} testid="src-automatch"
                         onChange={(v) => setForm({ ...form, allow_source_auto_match: v })} />
            </div>

            <div className="lg:col-span-5 border border-border rounded-lg p-4">
              <div className="font-medium text-sm mb-3">Collection Settings</div>
              <div className="grid grid-cols-2 gap-3">
                <FieldWithLabel label="Collection Frequency" required testid="src-freq">
                  <select value={form.collection_frequency}
                          onChange={(e) => setForm({ ...form, collection_frequency: e.target.value })}
                          className="w-full border border-border rounded px-2 py-1.5 text-sm"
                          data-testid="select-source-frequency">
                    <option value="manual">Manual</option>
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                  </select>
                </FieldWithLabel>
                <FieldWithLabel label="Parser Version" testid="src-parser"
                                hint="Leave default unless advised">
                  <input value={form.parser_version || "1.0"}
                         onChange={(e) => setForm({ ...form, parser_version: e.target.value })}
                         className="w-full border border-border rounded px-2 py-1.5 text-sm"
                         data-testid="input-source-parser" />
                </FieldWithLabel>
              </div>
            </div>

            <div className="lg:col-span-4 border border-border rounded-lg p-4 bg-[#F7FAF8]">
              <div className="flex items-center gap-2 font-medium text-sm mb-2">
                <Info className="w-4 h-4 text-[#2A5B46]" />
                What happens next?
              </div>
              <ul className="space-y-1.5 text-xs text-muted-foreground">
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#2A5B46] mt-0.5 flex-shrink-0" />
                  We save the source homepage.
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#2A5B46] mt-0.5 flex-shrink-0" />
                  We save only the confirmed listing page URLs.
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#2A5B46] mt-0.5 flex-shrink-0" />
                  The collector will use these exact URLs without guessing page names.
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border p-5 flex items-center justify-between bg-[#FAFBFA] rounded-b-lg">
          <div className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5" />
            This step confirms listing page addresses only.
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose}
                    className="px-4 py-2 text-sm rounded border border-border hover:bg-white"
                    data-testid="cancel-source">
              Cancel
            </button>
            <button onClick={save} disabled={saving}
                    className="px-5 py-2 text-sm rounded bg-[#2A5B46] text-white hover:bg-[#204838] disabled:opacity-60 flex items-center gap-1.5"
                    data-testid="save-source">
              <Save className="w-4 h-4" />
              {saving ? "Saving…" : "Save Source"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


function DiscoveryPanel({ discovering, discovery, discovered, confirmed,
                          onToggle, onRun, canDiscover, initial }) {
  const rows = discovered || [];
  const foundCount = rows.length;
  const hasResults = discovery?.ok || (initial?.listing_pages?.length > 0);

  return (
    <div className="border border-border rounded-lg h-full">
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="font-semibold" data-testid="discovery-title">Discovered Listing Pages</div>
          {hasResults && (
            <span className="text-xs bg-[#E7F1EB] text-[#1F5A3C] px-2 py-0.5 rounded-full"
                  data-testid="discovery-count-badge">
              {foundCount} found
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground mt-1">
          {hasResults
            ? `Scanned ${discovery?.pages_scanned ?? "the"} website pages and verified the following listing candidates.`
            : "Enter a base URL and click Discover Pages to scan the site's real navigation."}
        </div>
      </div>

      {discovering && (
        <div className="p-8 text-center text-sm text-muted-foreground" data-testid="discovery-loading">
          Intelligently traversing website pages and subpages, then verifying property listing grids…
        </div>
      )}

      {!discovering && !hasResults && (
        <div className="p-8 text-center text-sm text-muted-foreground" data-testid="discovery-empty">
          <Globe className="w-10 h-10 mx-auto text-muted-foreground/40 mb-3" />
          Nothing scanned yet. The scraper will only use URLs you confirm here.
        </div>
      )}

      {!discovering && hasResults && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#FAFBFA]">
              <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Detected URL</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Cards Found</th>
                <th className="py-3 px-4 text-right">Detail Links</th>
                <th className="py-3 px-4">AI Assessment</th>
                <th className="py-3 px-4 text-center">Confirm</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => {
                const Icon = CATEGORY_ICON[c.category] || Globe;
                const isOk = c.accessible !== false && (c.status || 200) < 400;
                return (
                  <tr key={c.listing_url}
                      className="border-t border-border/60 hover:bg-muted/30"
                      data-testid={`discover-row-${c.category || c.category_label}`}>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-[#F1F6F3] flex items-center justify-center flex-shrink-0">
                          <Icon className="w-4 h-4 text-[#2A5B46]" />
                        </div>
                        <div>
                          <div className="font-medium">{c.category_label}</div>
                          {c.link_text && (
                            <div className="text-[11px] text-muted-foreground truncate max-w-[160px]">
                              {c.link_text}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <a href={c.listing_url} target="_blank" rel="noopener noreferrer"
                         className="text-xs text-[#2A5B46] underline flex items-center gap-1 break-all"
                         data-testid={`discover-url-${c.category}`}>
                        {c.listing_url}
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    </td>
                    <td className="py-3 px-4">
                      {isOk ? (
                        <div className="flex items-center gap-1 text-emerald-700">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span className="text-xs">{c.status || 200} OK</span>
                        </div>
                      ) : (
                        <div className="text-xs text-red-600">{c.status || "err"}</div>
                      )}
                      <div className="text-[10px] text-muted-foreground">
                        {isOk ? "Accessible" : "Unreachable"}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right tabular-nums">{c.cards_found ?? 0}</td>
                    <td className="py-3 px-4 text-right tabular-nums">{c.detail_links ?? 0}</td>
                    <td className="py-3 px-4 text-xs">
                      <div className={c.canonical ? "text-emerald-700 font-medium" : "text-muted-foreground"}>
                        {c.canonical ? "Canonical" : c.verified_listing_page ? "Covered subpage" : "Low confidence"}
                        {typeof c.confidence === "number" ? ` · ${c.confidence}%` : ""}
                      </div>
                      <div className="text-[10px] text-muted-foreground max-w-[190px]">
                        {c.selection_reason || (c.covered_by ? `Covered by ${c.covered_by}` : "Staff review required")}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <input type="checkbox"
                             checked={!!confirmed[c.listing_url]}
                             onChange={() => onToggle(c.listing_url)}
                             className="w-4 h-4 accent-[#2A5B46]"
                             data-testid={`confirm-${c.category}`} />
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 px-4 text-center text-sm text-muted-foreground">
                    <ChevronRight className="w-4 h-4 inline mr-1" />
                    Discovery ran but found no navigation links matching a property category.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {hasResults && (
        <div className="p-3 border-t border-border bg-[#FAFBFA] flex items-center gap-2 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5" />
          Canonical listing pages are selected automatically. Covered type and location subpages remain visible but unselected to prevent duplicate collection.
          {discovery?.scan_truncated && (
            <span className="ml-1 text-amber-700">
              Scan reached its safety limit of {discovery.scan_limit} pages; results may be incomplete.
            </span>
          )}
        </div>
      )}
    </div>
  );
}


function FieldWithLabel({ label, required, hint, children, testid }) {
  return (
    <div data-testid={`field-${testid}`}>
      <div className="text-sm font-medium mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </div>
      {children}
      {hint && <div className="text-[11px] text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}

function ToggleRow({ label, hint, checked, onChange, testid }) {
  return (
    <label className="flex items-start gap-2 cursor-pointer" data-testid={`toggle-${testid}`}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
             className="w-4 h-4 mt-0.5 accent-[#2A5B46]" />
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-[11px] text-muted-foreground">{hint}</div>
      </div>
    </label>
  );
}
