import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";

const reqState = (id) => ({ requirement_id: id });

export default function Requirements() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/requirements").then((r) => setItems(r.data)); }, []);
  return (
    <div>
      <h1 className="text-2xl font-semibold">Property requirements</h1>
      <p className="text-sm text-muted-foreground">Buyer &amp; tenant briefs captured from Property Wanted, Corporate, and manual entry.</p>
      <div className="mt-4 grid md:grid-cols-2 gap-3">
        {items.map((r) => (
          <div key={r.id} className="bg-white rounded-lg border border-border p-4" data-testid={`req-${r.id}`}>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2 py-0.5 rounded-full bg-sand-100 capitalize">{r.intent}</span>
              <span className="px-2 py-0.5 rounded-full bg-sand-100 capitalize">{r.property_type || "any"}</span>
              {r.is_corporate && <span className="px-2 py-0.5 rounded-full bg-pine-500 text-white">Corporate</span>}
              <span className="ml-auto text-muted-foreground">{(r.created_at||"").slice(0,10)}</span>
            </div>
            <div className="font-medium mt-2">{r.customer_name || "Anonymous"}</div>
            <div className="text-sm text-ink-700 mt-1">Budget: {(r.min_price||0).toLocaleString()} – {(r.max_price||0).toLocaleString()} PGK · {r.min_bedrooms}+ beds</div>
            <div className="text-xs text-muted-foreground mt-1">{(r.locations||[]).join(", ") || "Any location"}</div>
            <div className="text-sm text-ink-700 mt-2">{r.notes}</div>
            <Link to="/admin/matching" state={reqState(r.id)} className="mt-3 inline-block text-sm text-pine-500 hover:underline" data-testid={`match-btn-${r.id}`}>Run matching →</Link>
          </div>
        ))}
      </div>
    </div>
  );
}
