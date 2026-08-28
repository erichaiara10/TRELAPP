import React from "react";
import { Edit2, Archive, RotateCcw, Inbox } from "lucide-react";
import { money } from "@/lib/api";

export default function PropertiesTable({ items, onEdit, onArchive, onRestore }) {
  if (!items || items.length === 0) {
    return (
      <div
        className="bg-white rounded-lg border border-dashed border-sand-200 py-16 text-center"
        data-testid="properties-empty"
      >
        <Inbox className="w-8 h-8 mx-auto text-muted-foreground" />
        <p className="mt-3 font-medium text-ink-700">No properties found</p>
        <p className="text-xs text-muted-foreground mt-1">
          Click <span className="font-medium">New</span> above to create your first listing,
          or use <span className="font-medium">Import CSV</span> to load them in bulk.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="p-3">Title</th><th className="p-3">Type</th><th className="p-3">Location</th>
            <th className="p-3">Price</th><th className="p-3">Status</th><th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id} className="border-t border-border hover:bg-sand-50/50" data-testid={`prop-row-${p.id}`}>
              <td className="p-3 font-medium">{p.title}</td>
              <td className="p-3 capitalize">{p.listing_type} · {p.property_type}</td>
              <td className="p-3">{p.suburb ? `${p.suburb}, ` : ""}{p.location}</td>
              <td className="p-3">{money(p.price, p.currency)}</td>
              <td className="p-3"><span className="px-2 py-0.5 rounded-full text-xs bg-sand-100 capitalize">{p.status}</span></td>
              <td className="p-3 text-right whitespace-nowrap">
                <button onClick={() => onEdit(p)} aria-label={`Edit ${p.title}`} title={`Edit ${p.title}`} data-testid={`edit-${p.id}`} className="p-1.5 hover:bg-sand-100 rounded"><Edit2 className="w-4 h-4" /></button>
                {p.archived || p.status === "archived"
                  ? <button onClick={() => onRestore(p.id)} aria-label={`Restore ${p.title}`} title={`Restore ${p.title}`} data-testid={`restore-${p.id}`} className="p-1.5 hover:bg-sand-100 rounded text-pine-600"><RotateCcw className="w-4 h-4" /></button>
                  : <button onClick={() => onArchive(p.id)} aria-label={`Archive ${p.title}`} title={`Archive ${p.title}`} data-testid={`archive-${p.id}`} className="p-1.5 hover:bg-sand-100 rounded text-destructive"><Archive className="w-4 h-4" /></button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
