import React, { useRef, useState } from "react";
import { FileUp, Loader2, X } from "lucide-react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";

const TYPES = [
  ["AUTHORITY_LETTER", "Authority letter"],
  ["TITLE_DOCUMENT", "Title document"],
  ["OWNER_ID", "Owner identification"],
  ["LEASE_DOCUMENT", "Lease document"],
  ["OTHER", "Other"],
];

export default function DocumentUploader({ value = [], onChange }) {
  const [documentType, setDocumentType] = useState("AUTHORITY_LETTER");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/documents/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onChange([
        ...value,
        {
          document_type: documentType,
          url: data.url,
          name: data.name || file.name,
          status: "UPLOADED",
        },
      ]);
      toast.success("Document uploaded");
    } catch (error) {
      toast.error(formatError(error));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="md:col-span-2" data-testid="property-documents">
      <div className="text-xs uppercase tracking-widest text-muted-foreground">
        Supporting documents
      </div>
      <div className="text-xs text-muted-foreground/80 mt-0.5">
        Authority, title, lease or owner-identification documents · PDF/JPG/PNG/WebP · 10 MB
      </div>
      <div className="mt-2 flex flex-col sm:flex-row gap-2">
        <select
          value={documentType}
          onChange={(event) => setDocumentType(event.target.value)}
          className="border border-border rounded-lg px-3 py-2.5 bg-white text-sm"
          data-testid="property-document-type"
        >
          {TYPES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
        <label className="inline-flex items-center justify-center gap-2 border-2 border-dashed border-border rounded-lg px-4 py-2.5 bg-white cursor-pointer">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,image/jpeg,image/png,image/webp"
            className="hidden"
            disabled={busy}
            onChange={(event) => upload(event.target.files?.[0])}
            data-testid="property-document-input"
          />
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileUp className="w-4 h-4" />}
          {busy ? "Uploading…" : "Upload document"}
        </label>
      </div>
      {!!value.length && (
        <div className="mt-2 space-y-1">
          {value.map((item, index) => (
            <div key={item.url || index} className="flex items-center justify-between gap-2 border border-border rounded px-3 py-2 text-sm bg-white">
              <span className="truncate">{item.name || item.document_type}</span>
              <button
                type="button"
                onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}
                aria-label="Remove document"
                data-testid={`property-document-remove-${index}`}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
