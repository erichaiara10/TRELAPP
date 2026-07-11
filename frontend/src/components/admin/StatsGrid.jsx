import React from "react";
import { Link } from "react-router-dom";

const STATS = [
  { key: "properties_active", label: "Active properties", to: "/admin/properties" },
  { key: "leads_new", label: "New leads", to: "/admin/leads" },
  { key: "inspections_open", label: "Open inspections", to: "/admin/inspections" },
  { key: "tasks_open", label: "Open tasks", to: "/admin/tasks" },
  { key: "customers", label: "Customers", to: "/admin/customers" },
  { key: "requirements_active", label: "Active requirements", to: "/admin/requirements" },
  { key: "properties_sold", label: "Sold" },
  { key: "properties_leased", label: "Leased" },
];

function Stat({ label, value, to }) {
  const testId = `stat-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const cls = "bg-white rounded-lg border border-border p-4 hover:shadow-sm block";
  const content = (
    <>
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-3xl font-semibold mt-1">{value}</div>
    </>
  );
  return to
    ? <Link to={to} className={cls} data-testid={testId}>{content}</Link>
    : <div className={cls} data-testid={testId}>{content}</div>;
}

export default function StatsGrid({ summary }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {STATS.map((s) => (
        <Stat key={s.key} label={s.label} value={summary[s.key] ?? "–"} to={s.to} />
      ))}
    </div>
  );
}
