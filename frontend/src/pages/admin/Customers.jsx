import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Customers() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/customers").then((r) => setItems(r.data)); }, []);
  return (
    <div>
      <h1 className="text-2xl font-semibold">Customers</h1>
      <p className="text-sm text-muted-foreground">CRM records created from public forms and manual entry.</p>
      <div className="mt-4 bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr><th className="p-3">Name</th><th className="p-3">Type</th><th className="p-3">Email</th><th className="p-3">Phone</th><th className="p-3">Source</th><th className="p-3">Created</th></tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="border-t border-border hover:bg-sand-50/50" data-testid={`cust-row-${c.id}`}>
                <td className="p-3 font-medium">{c.name}</td>
                <td className="p-3"><span className="px-2 py-0.5 rounded-full text-xs bg-sand-100 capitalize">{c.customer_type}</span></td>
                <td className="p-3">{c.email || "—"}</td>
                <td className="p-3">{c.phone || "—"}</td>
                <td className="p-3 text-xs">{c.source}</td>
                <td className="p-3 text-xs text-muted-foreground">{(c.created_at || "").slice(0,10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
