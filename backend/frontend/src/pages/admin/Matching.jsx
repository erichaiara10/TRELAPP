import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, money } from "@/lib/api";

export default function Matching() {
  const [reqs, setReqs] = useState([]);
  const [selectedId, setSelectedId] = useState(useLocation().state?.requirement_id || "");
  const [result, setResult] = useState(null);

  useEffect(() => { api.get("/requirements").then((r) => setReqs(r.data)); }, []);
  useEffect(() => {
    if (!selectedId) return;
    api.get(`/matching/${selectedId}`).then((r) => setResult(r.data));
  }, [selectedId]);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Property matching</h1>
      <div className="mt-3">
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} data-testid="match-req-select" className="border border-border rounded px-3 py-2 bg-white">
          <option value="">— Choose a requirement —</option>
          {reqs.map((r) => {
            const name = r.customer_name || "Anon";
            const price = (r.max_price || 0).toLocaleString();
            return (
              <option key={r.id} value={r.id}>
                {`${name} · ${r.intent} · ${price} PGK`}
              </option>
            );
          })}
        </select>
      </div>
      {result && (
        <div className="mt-6">
          <div className="text-sm text-muted-foreground">Requirement notes: <span className="text-ink-700">{result.requirement.notes}</span></div>
          <div className="mt-4 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {result.matches.map(({ property: p, score }) => (
              <div key={p.id} className="bg-white rounded-lg border border-border overflow-hidden" data-testid={`match-${p.id}`}>
                <div className="aspect-video bg-sand-100 overflow-hidden">
                  <img src={p.images?.[0]} alt="" className="w-full h-full object-cover" />
                </div>
                <div className="p-3">
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-sm">{p.title}</div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-pine-500 text-white">Score {score}</span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{p.suburb ? `${p.suburb}, `:""}{p.location}</div>
                  <div className="text-sm mt-1">{money(p.price, p.currency||"PGK")}</div>
                </div>
              </div>
            ))}
            {result.matches.length === 0 && <div className="text-sm text-muted-foreground">No matches.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
