// Hausples Selector Tester — modal launched from a hausples_png source row.
// Paste a URL, optionally override selectors, hit Test, see per-field match
// counts + samples. Speeds up parser tuning without touching the collector.
import React, { useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";

const DEFAULT_SELECTORS = {
  card:     ".listing-card, .property-card, article",
  url:      "a.listing-link, a.card-link, a[href*='/property/']",
  title:    ".listing-title, .card-title, h3",
  price:    ".listing-price, .price, .card-price",
  address:  ".listing-address, .address, .card-address",
  beds:     ".listing-beds, .beds",
  baths:    ".listing-baths, .baths",
  land:     ".listing-land, .land-area",
  building: ".listing-building, .building-area",
};

export default function HausplesSelectorTester({ source, onClose }) {
  const [url, setUrl] = useState(source?.base_url
    ? `${source.base_url.replace(/\/$/, "")}/property-for-sale`
    : "https://www.hausples.com.pg/property-for-sale");
  const [selectors, setSelectors] = useState({
    ...DEFAULT_SELECTORS,
    ...(source?.parser_config || {}),
  });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const runTest = async () => {
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post("/admin/market/collectors/hausples_png/test",
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

  const reset = () => setSelectors(DEFAULT_SELECTORS);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
         onClick={onClose} data-testid="hausples-tester-modal">
      <div className="bg-white rounded-lg p-5 w-full max-w-4xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Selector Tester</div>
            <div className="text-xl font-semibold mt-1">Hausples PNG</div>
            <div className="text-sm text-muted-foreground mt-1">
              Paste a search-results URL and tune the selectors until you see the field counts you expect. Nothing gets saved unless you copy the working selectors back into the source's parser_config.
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
            <button onClick={runTest} disabled={busy}
                    className="px-4 py-1.5 rounded bg-[#2A5B46] text-white text-sm hover:bg-[#204838] disabled:opacity-60"
                    data-testid="tester-run">
              {busy ? "Probing…" : "Test Selectors"}
            </button>
          </div>
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
        <div className="mt-2 text-right">
          <button onClick={reset} className="text-xs underline text-muted-foreground"
                  data-testid="tester-reset">Reset to defaults</button>
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
                <div className="flex items-center gap-4 text-sm mb-3">
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
                            {info.selector}
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
