// 9. Configuration — versioned parameter registry (MATCH-1.0 + GUIDE-1.0).
// Full CRUD backed by /api/admin/market/config. Parameter tuning UI (sliders,
// range inputs, save-as-new-version) uses JSON edit for now; per-parameter
// visual controls ship with Phase G governance.
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, formatError } from "@/lib/api";
import { PageHeader, Section } from "./_shared";

export default function MarketConfig() {
  const [versions, setVersions] = useState([]);
  const [active, setActive] = useState(null);
  const [draftName, setDraftName] = useState("");
  const [draftParams, setDraftParams] = useState("");

  const load = async () => {
    const [{ data: list }, { data: a }] = await Promise.all([
      api.get("/admin/market/config"),
      api.get("/admin/market/config/active?algorithm=combined").catch(() => ({ data: null })),
    ]);
    setVersions(list || []);
    setActive(a);
    if (a) setDraftParams(JSON.stringify(a.parameters, null, 2));
  };
  useEffect(() => { load().catch(() => {}); }, []);

  const activate = async (id) => {
    try { await api.post(`/admin/market/config/${id}/activate`); toast.success("Activated"); load(); }
    catch (e) { toast.error(formatError(e)); }
  };

  const saveNewVersion = async () => {
    let parsed;
    try { parsed = JSON.parse(draftParams); }
    catch { toast.error("Parameters must be valid JSON"); return; }
    if (!draftName.trim()) { toast.error("Version name required (e.g. COMBINED-1.1)"); return; }
    try {
      await api.post("/admin/market/config", {
        version: draftName.trim(), algorithm: "combined",
        parameters: parsed, notes: "Edited via admin UI", activate: true,
      });
      toast.success(`Version ${draftName} activated`);
      setDraftName(""); load();
    } catch (e) { toast.error(formatError(e)); }
  };

  return (
    <div data-testid="market-config-page">
      <PageHeader
        title="Configuration"
        subtitle="Versioned parameter registry for MATCH-1.0 + GUIDE-1.0. Every activation is audited and reversible via re-activation of a prior version."
      />

      <div className="grid lg:grid-cols-3 gap-4">
        <div>
          <Section title="Versions" testid="config-versions">
            {versions.length === 0 ? (
              <div className="text-sm text-muted-foreground">No configuration versions yet.</div>
            ) : (
              <div className="divide-y divide-border">
                {versions.map((v) => (
                  <div key={v.id} className="py-2 flex items-center justify-between" data-testid={`config-version-${v.version}`}>
                    <div>
                      <div className="font-medium">{v.version}</div>
                      <div className="text-xs text-muted-foreground">{v.algorithm}{v.active ? " · active" : ""}</div>
                    </div>
                    {!v.active && (
                      <button onClick={() => activate(v.id)}
                              className="text-xs underline" data-testid={`activate-${v.version}`}>Activate</button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>

        <div className="lg:col-span-2">
          <Section title={active ? `Active: ${active.version}` : "No active configuration"} testid="config-active">
            {active ? (
              <div>
                <div className="text-xs text-muted-foreground mb-2">Notes: {active.notes || "—"}</div>
                <pre className="bg-muted/40 rounded p-3 text-xs overflow-x-auto max-h-96" data-testid="config-json">
{JSON.stringify(active.parameters, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Publish a version to make it active.</div>
            )}
          </Section>

          <div className="mt-4">
            <Section title="Publish New Version" testid="config-new-version">
              <div className="space-y-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Version name</div>
                  <input value={draftName} onChange={(e) => setDraftName(e.target.value)}
                         placeholder="e.g. COMBINED-1.1"
                         className="w-full border border-border rounded px-2 py-1.5" data-testid="input-config-version" />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Parameters (JSON)</div>
                  <textarea value={draftParams} onChange={(e) => setDraftParams(e.target.value)}
                            rows={16} className="w-full border border-border rounded px-2 py-1.5 font-mono text-xs" data-testid="input-config-params" />
                </div>
                <div className="flex justify-end">
                  <button onClick={saveNewVersion}
                          className="px-3 py-1.5 rounded bg-[#2A5B46] text-white text-sm" data-testid="publish-config-btn">
                    Save & Activate
                  </button>
                </div>
              </div>
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}
