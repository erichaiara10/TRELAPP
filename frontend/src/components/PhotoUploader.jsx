import React, { useState, useRef } from "react";
import { api, formatError } from "@/lib/api";
import { Camera, X, Loader2 } from "lucide-react";
import { toast } from "sonner";

const MAX_FILES = 6;
const ACCEPT = "image/jpeg,image/png,image/webp";

/**
 * Multi-photo uploader for public forms.
 * Value is an array of uploaded photo objects: [{ id, url }]
 * Calls onChange(nextArray) after every add/remove.
 */
export default function PhotoUploader({ value = [], onChange, label = "Property photos", testId = "photo-upload" }) {
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const handleFiles = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    const remaining = MAX_FILES - value.length;
    if (remaining <= 0) { toast.error(`Maximum ${MAX_FILES} photos`); return; }
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

  const remove = (id) => onChange(value.filter((p) => p.id !== id));

  return (
    <div className="md:col-span-2" data-testid={testId}>
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-xs text-muted-foreground/80 mt-0.5">Up to {MAX_FILES} images · JPG, PNG or WebP · max 10 MB each</div>
      <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
        {value.map((p) => (
          <div key={p.id} className="relative aspect-square rounded-lg overflow-hidden border border-border bg-sand-100 group" data-testid={`${testId}-tile-${p.id}`}>
            <img src={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} alt={p.name || "Property photo"} className="w-full h-full object-cover" />
            <button type="button" onClick={() => remove(p.id)} data-testid={`${testId}-remove-${p.id}`}
              className="absolute top-1 right-1 p-1 rounded-full bg-white/95 hover:bg-white shadow" aria-label="Remove photo">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
        {value.length < MAX_FILES && (
          <label
            className={`aspect-square rounded-lg border-2 border-dashed border-border grid place-items-center cursor-pointer bg-white hover:bg-sand-50 transition-colors ${busy ? "opacity-60 pointer-events-none" : ""}`}
            data-testid={`${testId}-dropzone`}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              multiple
              onChange={(e) => handleFiles(e.target.files)}
              className="hidden"
              data-testid={`${testId}-input`}
            />
            <div className="flex flex-col items-center gap-1 text-muted-foreground text-xs px-2 text-center">
              {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Camera className="w-5 h-5" />}
              <span>{busy ? "Uploading…" : "Add photo"}</span>
            </div>
          </label>
        )}
      </div>
    </div>
  );
}
