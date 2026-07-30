import React, { useEffect, useRef, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import {
  Download, Upload, FileText, ChevronDown, ChevronUp, X, Loader2,
} from "lucide-react";

const TYPE_BADGES = {
  mandatory:   "bg-destructive/10 text-destructive",
  conditional: "bg-amber-100 text-amber-800",
  optional:    "bg-sand-100 text-muted-foreground",
  auto:        "bg-blue-50 text-blue-700",
};

/**
 * CSV Import/Export toolbar — shared by admin Properties + Customers pages.
 *
 * Props:
 *   entity    — "properties" | "customers"
 *   entityLabel — Human-friendly plural, e.g. "Properties"
 *   onImported — callback fired after a successful import (used to reload the table)
 */
export default function CsvToolbar({ entity, entityLabel, onImported }) {
  const [schema, setSchema] = useState(null);
  const [showGuide, setShowGuide] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    api.get(`/admin/${entity}/csv/schema`).then((r) => setSchema(r.data)).catch(() => {});
  }, [entity]);

  const download = async (kind) => {
    // kind is "" (full export) or "template"
    const url = `/admin/${entity}/csv${kind ? "/template" : ""}`;
    try {
      const r = await api.get(url, { responseType: "blob" });
      const blob = new Blob([r.data], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = kind === "template"
        ? `${entity}_template.csv`
        : `${entity}_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { toast.error(formatError(e)); }
  };

  const doImport = async (file) => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api.post(`/admin/${entity}/csv`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (fileRef.current) fileRef.current.value = "";  // clear so re-import works cleanly
      setResult(r.data);
      if (r.data.inserted > 0) {
        toast.success(`Imported ${r.data.inserted} rows`);
        onImported && onImported();
      } else if (r.data.errors?.length) {
        toast.error(`Imported 0 rows — see the report`);
      }
    } catch (e) { toast.error(formatError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="mb-4" data-testid={`csv-toolbar-${entity}`}>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <button onClick={() => setUploadOpen(true)} data-testid={`csv-import-${entity}`}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-white hover:bg-sand-50 text-sm">
          <Upload className="w-4 h-4" /> Import CSV
        </button>
        <button onClick={() => download("")} data-testid={`csv-export-${entity}`}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-white hover:bg-sand-50 text-sm">
          <Download className="w-4 h-4" /> Export CSV
        </button>
        <button onClick={() => download("template")} data-testid={`csv-template-${entity}`}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-white hover:bg-sand-50 text-sm">
          <FileText className="w-4 h-4" /> Download template
        </button>
        <button onClick={() => setShowGuide((v) => !v)} data-testid={`csv-guide-toggle-${entity}`}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-white hover:bg-sand-50 text-sm ml-auto">
          {showGuide ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />} Import Guide
        </button>
      </div>

      {showGuide && schema && (
        <div className="bg-white border border-border rounded-lg p-4 mb-2" data-testid={`csv-guide-${entity}`}>
          <div className="text-sm text-muted-foreground mb-3">
            Fields marked <span className={`px-1.5 py-0.5 text-[10px] rounded ${TYPE_BADGES.mandatory}`}>Mandatory</span> must appear in the CSV header row.
            Fields marked <span className={`px-1.5 py-0.5 text-[10px] rounded ${TYPE_BADGES.conditional}`}>Conditional</span> are required only when a rule applies (see the Explanation column).
            List values use <code className="bg-sand-100 px-1 rounded">;</code> (semicolon) as a separator.
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-muted-foreground bg-sand-50">
                <tr>
                  <th className="p-2">Field Name</th>
                  <th className="p-2 w-32">Type</th>
                  <th className="p-2">Explanation</th>
                </tr>
              </thead>
              <tbody>
                {schema.fields.map((f) => (
                  <tr key={f.name} className="border-t border-border align-top">
                    <td className="p-2 font-mono text-xs">{f.name}</td>
                    <td className="p-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase tracking-widest ${TYPE_BADGES[f.type] || TYPE_BADGES.optional}`}>
                        {f.type}
                      </span>
                    </td>
                    <td className="p-2 text-sm">{f.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {uploadOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 grid place-items-center p-4"
             onClick={() => !busy && setUploadOpen(false)}>
          <div className="bg-white rounded-lg w-full max-w-lg" onClick={(e) => e.stopPropagation()}
               data-testid={`csv-import-modal-${entity}`}>
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="font-medium">Import {entityLabel}</div>
              <button onClick={() => !busy && setUploadOpen(false)} aria-label="Close"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-4 space-y-3 text-sm">
              <p className="text-muted-foreground">
                Upload a UTF-8 CSV. Rows will be <strong>appended</strong> to the existing records —
                nothing is overwritten. Rows with an existing <code>id</code> are skipped.
              </p>
              {schema && (
                <div className="text-xs bg-sand-50 border border-border rounded p-2">
                  <div className="uppercase tracking-widest text-muted-foreground mb-1">Required headers</div>
                  <div className="font-mono">{schema.required_headers.join(", ")}</div>
                </div>
              )}
              <input ref={fileRef} type="file" accept=".csv,text/csv"
                     data-testid={`csv-file-input-${entity}`}
                     className="block w-full text-sm border border-border rounded p-2" />
              {result && (
                <div className="border border-border rounded p-3 space-y-1 text-sm" data-testid={`csv-result-${entity}`}>
                  <div><strong>{result.inserted}</strong> inserted &nbsp;·&nbsp;
                    <strong>{result.skipped?.length || 0}</strong> skipped &nbsp;·&nbsp;
                    <strong className={result.errors?.length ? "text-destructive" : ""}>{result.errors?.length || 0}</strong> rejected</div>
                  {result.errors?.length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-destructive cursor-pointer">Show errors</summary>
                      <ul className="mt-1 text-xs list-disc pl-5 max-h-40 overflow-auto">
                        {result.errors.slice(0, 100).map((e, i) => (
                          <li key={i}>Row {e.row}: {e.reason}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {result.skipped?.length > 0 && (
                    <details>
                      <summary className="text-xs text-muted-foreground cursor-pointer">Show skipped</summary>
                      <ul className="mt-1 text-xs list-disc pl-5 max-h-40 overflow-auto">
                        {result.skipped.slice(0, 100).map((s, i) => (
                          <li key={i}>Row {s.row}: {s.reason}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )}
            </div>
            <div className="p-4 border-t border-border flex justify-end gap-2">
              <button disabled={busy} onClick={() => setUploadOpen(false)}
                      className="px-3 py-2 rounded-md border border-border text-sm disabled:opacity-60">
                {result ? "Close" : "Cancel"}
              </button>
              <button disabled={busy} data-testid={`csv-upload-submit-${entity}`}
                      onClick={() => doImport(fileRef.current?.files?.[0])}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-[#0F172A] text-white text-sm disabled:opacity-60">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                {busy ? "Importing…" : "Upload & Import"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
