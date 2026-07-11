import React from "react";
export default function Legal({ kind }) {
  const title = kind === "terms" ? "Terms and Conditions" : "Privacy Policy";
  return (
    <div className="container-tight py-14 max-w-3xl">
      <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Legal</div>
      <h1 className="font-serif text-5xl mt-3">{title}</h1>
      <div className="prose mt-6 text-ink-700 leading-relaxed space-y-4">
        {kind === "terms" ? (
          <>
            <p>By using the Triumph Real Estate Limited (TREL) website you agree to these terms. Content is provided for informational purposes and does not constitute a binding offer.</p>
            <p>Listings are believed to be accurate but should be independently verified. TREL is not liable for errors, omissions, or third-party actions.</p>
            <p>Users must not submit false information, harvest listings, or misuse contact channels. We reserve the right to suspend abusive access.</p>
          </>
        ) : (
          <>
            <p>Triumph Real Estate Limited (TREL) collects contact information you submit via our forms (name, email, phone, requirements) for the sole purpose of servicing your enquiry.</p>
            <p>We do not sell your data. Data may be shared with agents assigned to your enquiry. You may request deletion at any time by contacting us.</p>
            <p>Cookies are used only for functional purposes (session, preferences). No third-party ad tracking is performed.</p>
          </>
        )}
      </div>
    </div>
  );
}
