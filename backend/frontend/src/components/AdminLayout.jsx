import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, Building2, Users, Inbox, ClipboardList, Target, Calendar, ListChecks, KanbanSquare, UserCog, FileText, BarChart3, MapPin, LogOut, Database, Megaphone, UserRoundCheck, SendToBack, History, FileCheck2, ChevronDown, Gauge, Scale, TrendingUp, Globe2, CopyCheck, Calculator, ShieldAlert, Settings, ScrollText } from "lucide-react";
import { useAuth } from "@/lib/auth";

const items = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/properties", label: "Properties", icon: Building2 },
  { to: "/admin/customers", label: "Customers", icon: Users },
  { to: "/admin/leads", label: "Leads", icon: Inbox },
  { to: "/admin/requirements", label: "Requirements", icon: ClipboardList },
  { to: "/admin/matching", label: "Matching", icon: Target },
  { to: "/admin/inspections", label: "Inspections", icon: Calendar },
  { to: "/admin/tasks", label: "Tasks", icon: ListChecks },
  { to: "/admin/pipeline", label: "Pipeline", icon: KanbanSquare },
  { to: "/admin/users", label: "Users", icon: UserCog },
  { to: "/admin/locations", label: "Locations", icon: MapPin },
  { to: "/admin/content", label: "Content", icon: FileText },
  { to: "/admin/reports", label: "Reports", icon: BarChart3 },
  { to: "/admin/market/evidence", label: "Market Evidence", icon: Database },
];

const propertyAdvertisingItems = [
  { to: "/admin/property-advertising", label: "Overview", icon: Megaphone, end: true },
  { to: "/admin/property-advertising/advertisers", label: "Advertisers", icon: UserRoundCheck },
  { to: "/admin/property-advertising/submissions", label: "Properties & Submissions", icon: SendToBack },
  { to: "/admin/property-advertising/publications", label: "Publication Control", icon: FileCheck2 },
  { to: "/admin/property-advertising/lifecycle", label: "Listing Lifecycle", icon: History },
];

const propertyDataAggregationItems = [
  { to: "/admin/market", label: "Overview", icon: Gauge, end: true },
  { to: "/admin/market/evidence", label: "Market Evidence", icon: Database },
  { to: "/admin/market/comparables", label: "Comparable Properties", icon: Scale },
  { to: "/admin/market/trends", label: "Price Trends", icon: TrendingUp },
  { to: "/admin/market/sources", label: "Data Sources", icon: Globe2 },
  { to: "/admin/market/duplicates", label: "Duplicate Matches", icon: CopyCheck },
  { to: "/admin/market/price-compare-results", label: "Price Compare Results", icon: Calculator },
  { to: "/admin/market/review-cases", label: "Review Cases", icon: ShieldAlert },
  { to: "/admin/market/configuration", label: "Configuration", icon: Settings },
  { to: "/admin/market/audit-log", label: "Audit Log", icon: ScrollText },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const inPropertyAdvertising = location.pathname.startsWith("/admin/property-advertising");
  const inPropertyDataAggregation = location.pathname === "/admin/market" || location.pathname.startsWith("/admin/market/");
  const [operationsOpen, setOperationsOpen] = useState(!inPropertyAdvertising && !inPropertyDataAggregation);
  const [propertyAdvertisingOpen, setPropertyAdvertisingOpen] = useState(inPropertyAdvertising);
  const [propertyDataAggregationOpen, setPropertyDataAggregationOpen] = useState(inPropertyDataAggregation);

  useEffect(() => {
    if (inPropertyAdvertising) setPropertyAdvertisingOpen(true);
    else if (inPropertyDataAggregation) setPropertyDataAggregationOpen(true);
    else setOperationsOpen(true);
  }, [inPropertyAdvertising, inPropertyDataAggregation]);

  const handleLogout = async () => { await logout(); nav("/"); };

  const groupButton = (label, open, toggle, testId) => (
    <button type="button" onClick={toggle} aria-expanded={open} data-testid={testId}
      className="w-full flex items-center justify-between px-3 py-2 rounded-md text-xs font-semibold uppercase tracking-[0.14em] text-white/60 hover:bg-white/5 hover:text-white">
      <span>{label}</span>
      <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
  );

  return (
    <div className="min-h-screen flex bg-[#F3F4F6] text-[#111827]" style={{ fontFamily: "Outfit, sans-serif" }}>
      <aside className="sticky top-0 h-screen w-64 shrink-0 bg-[#0F172A] text-white flex flex-col" data-testid="admin-sidebar">
        <div className="px-5 py-5 border-b border-white/10">
          <div className="text-sm uppercase tracking-[0.3em] text-white/50">TREL</div>
          <div className="font-serif text-xl mt-1">Operations</div>
        </div>
        <nav className="p-3 flex-1 overflow-y-auto">
          {groupButton("Operations", operationsOpen, () => setOperationsOpen((open) => !open), "sidebar-group-operations")}
          {operationsOpen && <div data-testid="sidebar-group-operations-items" className="mt-1 mb-3">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors ${
                  isActive ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
                }`
              }
              data-testid={`sidebar-${it.to.replace("/admin","").replace("/","") || "dashboard"}`}
            >
              <it.icon className="w-4 h-4" />
              {it.label}
            </NavLink>
          ))}
          </div>}
          {groupButton("Property Advertising", propertyAdvertisingOpen, () => setPropertyAdvertisingOpen((open) => !open), "sidebar-group-property-advertising")}
          {propertyAdvertisingOpen && <div data-testid="sidebar-group-property-advertising-items" className="mt-1">
          {propertyAdvertisingItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors ${
                  isActive ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
                }`
              }
              data-testid={`sidebar-property-advertising-${it.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            >
              <it.icon className="w-4 h-4" />
              {it.label}
            </NavLink>
          ))}
          </div>}
          {groupButton("Property Data Aggregation", propertyDataAggregationOpen, () => setPropertyDataAggregationOpen((open) => !open), "sidebar-group-property-data-aggregation")}
          {propertyDataAggregationOpen && <div data-testid="sidebar-group-property-data-aggregation-items" className="mt-1">
          {propertyDataAggregationItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors ${
                  isActive ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
                }`
              }
              data-testid={`sidebar-property-data-aggregation-${it.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            >
              <it.icon className="w-4 h-4" />
              {it.label}
            </NavLink>
          ))}
          </div>}
        </nav>
        <div className="shrink-0 sticky bottom-0 bg-[#0F172A] p-4 border-t border-white/10 text-sm">
          <div className="font-medium">{user?.name}</div>
          <div className="text-xs text-white/60 mb-3">{user?.role}</div>
          <button onClick={handleLogout} data-testid="admin-logout-btn"
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-white/10 hover:bg-white/20">
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-6 overflow-y-auto" data-testid="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
