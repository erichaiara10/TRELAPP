import React, { useState, useRef } from "react";
import { api, formatError } from "@/lib/api";
import { Camera, X, Loader2, Star, Link as LinkIcon, Plus } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_MAX = 6;
const ACCEPT = "image/jpeg,image/png,image/webp";

/**
 * Multi-photo uploader.
 * Value is an array of photo entries: either { id, url, name } (from /public/upload)
 * or { url } (manually pasted external URL).
 * The FIRST entry is the "cover" photo.
 *
 * Props:
 *  - value, onChange (required)
 *  - max (default 6)
 *  - allowUrls (default false) — show a "Paste URL" input for adding external image URLs
 *  - allowCover (default false) — show "Set as cover" affordance on each tile
 *  - testId (default "photo-upload")
 */
export default function PhotoUploader({
  value = [], onChange, max = DEFAULT_MAX,
  allowUrls = false, allowCover = false, testId = "photo-upload",
  label = "Property photos",
}) {
  const [busy, setBusy] = useState(false);
  const [urlDraft, setUrlDraft] = useState("");
  const inputRef = useRef(null);

  const resolveDisplay = (p) => {
    if (!p?.url) return "";
    if (p.url.startsWith("http")) return p.url;
    // Backend-served path like /api/files/<id>
    return `${process.env.REACT_APP_BACKEND_URL}${p.url}`;
  };

  const handleFiles = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    const remaining = max - value.length;
    if (remaining <= 0) { toast.error(`Maximum ${max} photos`); return; }
    const files = Array.from(fileList).slice(0, remaining);
    setBusy(true);
    const uploaded = [];
    for (const file of files) {
      try {
        const fd = new FormData();
        fd.append("file", file);
        const { data } = await api.post("/public/upload", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        uploaded.push({ id: data.id, url: data.url, name: file.name });
      } catch (e) {
        toast.error(`${file.name}: ${formatError(e)}`);
      }
    }
    if (uploaded.length) onChange([...value, ...uploaded]);
    setBusy(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  const addUrl = () => {
    const u = urlDraft.trim();
    if (!u) return;
    if (!/^https?:\/\//i.test(u)) { toast.error("Please enter a full https:// URL"); return; }
    if (value.length >= max) { toast.error(`Maximum ${max} photos`); return; }
    onChange([...value, { url: u, name: "external" }]);
    setUrlDraft("");
  };

  const remove = (idx) => {
    const next = value.filter((_, i) => i !== idx);
    onChange(next);
  };

  const setCover = (idx) => {
    if (idx === 0) return;
    const next = [value[idx], ...value.filter((_, i) => i !== idx)];
    onChange(next);
    toast.success("Cover photo updated");
  };

  return (
    <div className="md:col-span-2" data-testid={testId}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-xs text-muted-foreground/80 mt-0.5">
        Up to {max} images · JPG, PNG or WebP · max 10 MB each
        {allowCover && <> · <span className="text-pine-500 font-medium">first image is the cover</span></>}
      </div>
      <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {value.map((p, idx) => (
          <div key={p.id || p.url || idx} className="relative aspect-square rounded-lg overflow-hidden border border-border bg-sand-100 group" data-testid={`${testId}-tile-${idx}`}>
            <img src={resolveDisplay(p)} alt={p.name || "Property photo"} className="w-full h-full object-cover" />
            {allowCover && idx === 0 && (
              <span className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-pine-500 text-white text-[10px] uppercase tracking-widest font-medium flex items-center gap-1" data-testid={`${testId}-cover-badge`}>
                <Star className="w-3 h-3 fill-current" /> Cover
              </span>
            )}
            <button type="button" onClick={() => remove(idx)} data-testid={`${testId}-remove-${idx}`}
              className="absolute top-1 right-1 p-1 rounded-full bg-white/95 hover:bg-white shadow" aria-label="Remove photo">
              <X className="w-3.5 h-3.5" />
            </button>
            {allowCover && idx !== 0 && (
              <button type="button" onClick={() => setCover(idx)} data-testid={`${testId}-set-cover-${idx}`}
                className="absolute bottom-1 left-1 right-1 px-2 py-1 rounded bg-black/70 text-white text-[10px] uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1">
                <Star className="w-3 h-3" /> Set as cover
              </button>
            )}
          </div>
        ))}
        {value.length < max && (
          <label
            className={`aspect-square rounded-lg border-2 border-dashed border-border grid place-items-center cursor-pointer bg-white hover:bg-sand-50 transition-colors ${busy ? "opacity-60 pointer-events-none" : ""}`}
            data-testid={`${testId}-dropzone`}
          >
            <input ref={inputRef} type="file" accept={ACCEPT} multiple onChange={(e) => handleFiles(e.target.files)} className="hidden" data-testid={`${testId}-input`} />
            <div className="flex flex-col items-center gap-1 text-muted-foreground text-xs px-2 text-center">
              {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
              <span>{busy ? "Uploading…" : "Upload photo"}</span>
            </div>
          </label>
        )}
      </div>
      {allowUrls && (
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 border border-border rounded-lg px-3 bg-white">
            <LinkIcon className="w-4 h-4 text-muted-foreground" />
            <input
              type="url"
              value={urlDraft}
              onChange={(e) => setUrlDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addUrl(); } }}
              placeholder="Or paste an image URL (https://…)"
              data-testid={`${testId}-url-input`}
              className="flex-1 py-2 outline-none text-sm bg-transparent"
            />
          </div>
          <button type="button" onClick={addUrl} data-testid={`${testId}-url-add`}
            className="px-3 py-2 rounded-lg bg-[#0F172A] text-white text-sm flex items-center gap-1">
            <Plus className="w-4 h-4" /> Add link
          </button>
        </div>
      )}
    </div>
  );
}
