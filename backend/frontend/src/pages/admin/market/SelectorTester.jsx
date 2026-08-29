// Selector Tester — generic modal launched from ANY HTTP-collector source row.
// Works uniformly across hausples_png, ljhookerpng, mypnghome, sre, dac,
// marketmeri. Paste a URL, optionally override selectors, hit Test, see
// per-field match counts + samples. Nothing is saved until the operator
// copies the working selectors into the source's `parser_config` themselves.
import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";

// Every field the backend probes — order matters (drives modal layout).
const FIELD_KEYS = ["card", "url", "title", "price", "address", "description",
                    "beds", "baths", "land", "building"];

function pickSelectorFields(cfg) {
  const out = {};
  for (const k of FIELD_KEYS) {
    if (cfg && cfg[k]) out[k] = cfg[k];
  }
  return out;
}

function firstSearchUrl(cfg, source) {
  const confirmed = (source?.listing_pages || []).find((p) => p?.listing_url)?.listing_url;
  if (confirmed) return confirmed;
  return source?.base_url || cfg?.base_url || "";
}

export default function SelectorTester({ source, collectorMeta, onClose }) {
  // Backend now returns default_config on /admin/market/collectors, but we
  // still handle the legacy case (no default_config → hit /defaults endpoint).
  const collectorKey = source?.collector;
  const collectorLabel = collectorMeta?.label || collectorKey || "Collector";
  const [defaults, setDefaults] = useState(collectorMeta?.default_config || null);
  const [url, setUrl] = useState("");
  const [selectors, setSelectors] = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      let cfg = collectorMeta?.default_config || null;
      if (!cfg && collectorKey) {
        try {
          const { data } = await api.get(`/admin/market/collectors/${collectorKey}/defaults`);
          cfg = data.default_config;
        } catch (e) {
          toast.error(formatError(e));
          return;
        }
      }
      if (cancelled || !cfg) return;
      setDefaults(cfg);
      setSelectors({
        ...pickSelectorFields(cfg),
        ...pickSelectorFields(source?.parser_config || {}),
      });
      setUrl(firstSearchUrl(cfg, source));
    };
    load();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectorKey]);

  const searchPaths = useMemo(() => (source?.listing_pages || []).map((p) => p.listing_url).filter(Boolean), [source]);

  const runTest = async () => {
    if (!collectorKey) return;
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post(`/admin/market/collectors/${collectorKey}/test`,
        { url, selectors });
      setResult(data);
      if (data.ok) {
        toast.success(`${data.cards_found} card${data.cards_found === 1 ? "" : "s"} found`);
      } else {
        toast.error(data.error?.slice(0, 120) || "Probe failed");
      }
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  const reset = () => {
    if (!defaults) return;
    setSelectors(pickSelectorFields(defaults));
    toast.info(`Reset to ${collectorLabel} defaults`);
  };

  const saveToSource = async () => {
    if (!source?.id) { toast.error("No source associated with this test session"); return; }
    setBusy(true);
    try {
      await api.post(`/admin/market/sources/${source.id}/parser-config`,
                     { parser_config: selectors });
      toast.success(`Selectors saved to "${source.name}"`);
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  if (!defaults) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
           onClick={onClose} data-testid="selector-tester-modal">
        <div className="bg-white rounded-lg p-5 w-full max-w-md text-center"
             onClick={(e) => e.stopPropagation()}>
          <div className="text-sm text-muted-foreground">Loading collector defaults…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
         onClick={onClose} data-testid="selector-tester-modal">
      <div className="bg-white rounded-lg p-5 w-full max-w-4xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Selector Tester</div>
            <div className="text-xl font-semibold mt-1" data-testid="tester-collector-label">
              {collectorLabel}
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              Paste a search-results URL and tune the selectors until you see the field counts you expect. Nothing gets saved unless you copy the working selectors back into the source's <code>parser_config</code>.
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"
                  data-testid="tester-close">✕</button>
        </div>

        <label className="block text-sm">
          <div className="text-xs text-muted-foreground mb-1">Search-results URL</div>
          <div className="flex gap-2">
            <input value={url} onChange={(e) => setUrl(e.target.value)}
                   className="flex-1 border border-border rounded px-2 py-1.5"
                   data-testid="tester-url" />
            <button onClick={runTest} disabled={busy || !url}
                    className="px-4 py-1.5 rounded bg-[#2A5B46] text-white text-sm hover:bg-[#204838] disabled:opacity-60"
                    data-testid="tester-run">
              {busy ? "Probing…" : "Test Selectors"}
            </button>
          </div>
          {searchPaths.length > 0 && (
            <div className="mt-1.5 text-[11px] text-muted-foreground" data-testid="tester-quick-paths">
              Quick paths:{" "}
              {searchPaths.map((p, i) => (
                <button key={p} type="button"
                        onClick={() => setUrl(p)}
                        className="underline mr-2 hover:text-foreground"
                        data-testid={`tester-path-${i}`}>
                  {p}
                </button>
              ))}
            </div>
          )}
        </label>

        <div className="grid md:grid-cols-2 gap-3 mt-4">
          {Object.entries(selectors).map(([k, v]) => (
            <label key={k} className="block text-sm" data-testid={`tester-field-${k}`}>
              <div className="text-xs text-muted-foreground mb-1 capitalize">{k}</div>
              <input value={v} onChange={(e) => setSelectors({ ...selectors, [k]: e.target.value })}
                     className="w-full border border-border rounded px-2 py-1.5 font-mono text-xs"
                     data-testid={`tester-input-${k}`} />
            </label>
          ))}
        </div>
        <div className="mt-2 flex items-center justify-between">
          <button onClick={reset} className="text-xs underline text-muted-foreground"
                  data-testid="tester-reset">Reset to defaults</button>
          <button onClick={saveToSource} disabled={busy || !source?.id}
                  className="px-3 py-1 text-xs rounded border border-[#2A5B46] text-[#2A5B46] hover:bg-[#F1F6F3] disabled:opacity-50"
                  data-testid="tester-save-to-source">
            Save to source
          </button>
        </div>

        {result && (
          <div className="mt-5 border-t border-border pt-4" data-testid="tester-result">
            {!result.ok ? (
              <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-800"
                   data-testid="tester-error">
                <div className="font-medium">Probe failed</div>
                <div className="text-xs mt-1 font-mono break-all">{result.error}</div>
                <div className="text-xs mt-2 text-red-600">
                  Try a different URL — this is exactly what happens on a live scrape when the
                  path 404s or blocks the collector.
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center flex-wrap gap-x-4 gap-y-1 text-sm mb-3">
                  <div>HTTP <strong>{result.http_status}</strong></div>
                  <div>{result.html_bytes?.toLocaleString()} bytes</div>
                  <div>Card selector <span className="font-mono text-xs">{result.card_selector}</span></div>
                  <div>
                    Cards found:{" "}
                    <strong className={result.cards_found > 0 ? "text-emerald-700" : "text-red-700"}
                            data-testid="tester-cards-found">
                      {result.cards_found}
                    </strong>
                  </div>
                </div>
                {result.cards_found === 0 ? (
                  <div className="text-sm text-muted-foreground">
                    No cards matched your <code className="font-mono">card</code> selector. Adjust it above and re-run —
                    field selectors won't match anything until this one lands.
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[11px] uppercase tracking-widest text-muted-foreground border-b border-border">
                        <th className="py-2 pr-3">Field</th>
                        <th className="py-2 pr-3">Selector</th>
                        <th className="py-2 pr-3 text-right">Match</th>
                        <th className="py-2 pr-3">Samples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(result.fields || {}).map(([field, info]) => (
                        <tr key={field} className="border-b border-border/60"
                            data-testid={`tester-row-${field}`}>
                          <td className="py-2 pr-3 font-medium capitalize">{field}</td>
                          <td className="py-2 pr-3 font-mono text-xs text-muted-foreground truncate max-w-xs">
                            {info.selector || <span className="italic text-muted-foreground">not configured</span>}
                          </td>
                          <td className={`py-2 pr-3 text-right tabular-nums ${info.matches === 0 ? "text-red-700" : "text-emerald-700"}`}>
                            {info.matches} / {result.cards_found}{" "}
                            <span className="text-xs text-muted-foreground">({info.match_rate}%)</span>
                          </td>
                          <td className="py-2 pr-3 text-xs">
                            {info.samples.length === 0 ? (
                              <span className="text-muted-foreground">—</span>
                            ) : (
                              info.samples.map((s, i) => (
                                <div key={i} className="truncate max-w-md">{s}</div>
                              ))
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="mt-3 text-xs text-muted-foreground">
                  Happy with the result? Copy the selectors into the source's <code>parser_config</code> in the source modal — that persists them for every future collection run.
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
