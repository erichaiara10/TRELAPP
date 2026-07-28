import React, { useRef, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { Upload, X, Loader2, Link as LinkIcon } from "lucide-react";

/**
 * Single image uploader. `value` is a URL string; `onChange(url)` returns a URL string.
 * Supports direct file upload (to Emergent object storage via /api/public/upload)
 * and manual URL entry.
 */
export default function ImageField({ label = "Image", value = "", onChange, testId = "image-field", hint = "" }) {
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const resolve = (u) => (!u ? "" : u.startsWith("http") ? u : `${process.env.REACT_APP_BACKEND_URL}${u}`);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/public/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onChange(data.url);
      toast.success("Image uploaded");
    } catch (e) { toast.error(formatError(e)); }
    finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div data-testid={testId}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      {hint && <div className="text-[11px] text-muted-foreground/80 mt-0.5">{hint}</div>}
      <div className="mt-1.5 flex items-start gap-3">
        <div className="relative w-28 h-20 shrink-0 rounded-lg overflow-hidden border border-border bg-sand-50 grid place-items-center">
          {value ? (
            <img src={resolve(value)} alt={label} className="w-full h-full object-cover" data-testid={`${testId}-preview`} />
          ) : (
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest">No image</span>
          )}
          {value && (
            <button type="button" onClick={() => onChange("")} data-testid={`${testId}-clear`}
              className="absolute top-1 right-1 p-0.5 rounded-full bg-white/95 hover:bg-white shadow" aria-label="Remove">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
        <div className="flex-1 space-y-1.5">
          <label className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#0F172A] text-white text-sm cursor-pointer ${busy ? "opacity-60 pointer-events-none" : ""}`}>
            <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => upload(e.target.files?.[0])} className="hidden" data-testid={`${testId}-file`} />
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
            {busy ? "Uploading…" : "Upload"}
          </label>
          <div className="flex items-center gap-1 border border-border rounded-md px-2 bg-white">
            <LinkIcon className="w-3.5 h-3.5 text-muted-foreground" />
            <input
              type="url" placeholder="…or paste https:// URL"
              value={value || ""} onChange={(e) => onChange(e.target.value)}
              data-testid={`${testId}-url`}
              className="flex-1 py-1 text-xs outline-none bg-transparent"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
