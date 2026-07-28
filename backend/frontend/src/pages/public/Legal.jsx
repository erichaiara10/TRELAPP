import React from "react";
import { usePage } from "@/lib/usePage";

export default function Legal({ kind }) {
  const slug = kind === "terms" ? "legal_terms" : "legal_privacy";
  const { sections } = usePage(slug);
  const title = sections.title || (kind === "terms" ? "Terms of Service" : "Privacy Policy");
  const body = sections.body || "";

  return (
    <div className="container-tight py-14 max-w-3xl">
      <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Legal</div>
      <h1 className="font-serif text-4xl sm:text-5xl mt-3" data-testid={`legal-${kind || "privacy"}-title`}>{title}</h1>
      <div className="mt-6 text-ink-700 leading-relaxed whitespace-pre-line" data-testid={`legal-${kind || "privacy"}-body`}>
        {body}
      </div>
    </div>
  );
}
