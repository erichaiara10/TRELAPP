import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, Building2, Users, Inbox, ClipboardList, Target, Calendar, ListChecks, KanbanSquare, UserCog, FileText, BarChart3, MapPin, LogOut, Database, Megaphone, UserRoundCheck, SendToBack, History, FileCheck2, ChevronDown, Gauge, Scale, TrendingUp, Globe2, CopyCheck, Calculator, ShieldAlert, Settings, ScrollText, Menu, X } from "lucide-react";
import { useAuth } from "@/lib/auth";

const customerItems = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/customers", label: "Customer Register", icon: Users },
  { to: "/admin/properties", label: "Properties", icon: Building2 },
  { to: "/admin/leads", label: "Leads", icon: Inbox },
  { to: "/admin/requirements", label: "Requirements", icon: ClipboardList },
  { to: "/admin/matching", label: "Matching", icon: Target },
  { to: "/admin/inspections", label: "Inspections", icon: Calendar },
  { to: "/admin/tasks", label: "Tasks", icon: ListChecks },
  { to: "/admin/pipeline", label: "Pipeline", icon: KanbanSquare },
];
const administrationItems = [
  { to: "/admin/users", label: "Users & Permissions", icon: UserCog },
  { to: "/admin/content", label: "Website Content & Settings", icon: FileText },
  { to: "/admin/locations", label: "Locations", icon: MapPin },
  { to: "/admin/reports", label: "Reports", icon: BarChart3 },
];
const advertiserItems = [
  { to: "/admin/property-advertising", label: "Overview", icon: Megaphone, end: true },
  { to: "/admin/property-advertising/advertisers", label: "Advertisers", icon: UserRoundCheck },
  { to: "/admin/property-advertising/submissions", label: "Properties & Submissions", icon: SendToBack },
  { to: "/admin/property-advertising/publications", label: "Publication Control", icon: FileCheck2 },
  { to: "/admin/property-advertising/lifecycle", label: "Listing Lifecycle", icon: History },
  { to: "/admin/property-advertising/sale-progression", label: "Sale Progression", icon: KanbanSquare },
];

const marketItems = [
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

const groups = [
  { id: "trel-customers", label: "TREL Customers", items: customerItems },
  { id: "property-advertising", label: "Advertisers & Listings", items: advertiserItems },
  { id: "property-data-aggregation", label: "Market Intelligence", items: marketItems },
  { id: "administration", label: "Administration", items: administrationItems },
];
const activeGroup = (pathname) => groups.find((group) => group.items.some((item) =>
  item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)
))?.id || "trel-customers";

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const [openGroups, setOpenGroups] = useState(() => ({ [activeGroup(pathname)]: true }));
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setOpenGroups((open) => ({ ...open, [activeGroup(pathname)]: true }));
    setMobileOpen(false);
  }, [pathname]);
  useEffect(() => {
    if (!mobileOpen) return;
    const closeOnEscape = (event) => { if (event.key === "Escape") setMobileOpen(false); };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileOpen]);

  const handleLogout = async () => { await logout(); nav("/"); };

  return (
    <div className="min-h-screen flex bg-[#F3F7FA] text-[#111827]" style={{ fontFamily: "Outfit, sans-serif" }}>
      {mobileOpen && <button type="button" aria-label="Close staff navigation" onClick={() => setMobileOpen(false)} className="fixed inset-0 z-30 bg-black/40 lg:hidden" />}
      <aside id="staff-navigation" aria-label="Staff workspace navigation" className={`${mobileOpen ? "flex" : "hidden"} fixed inset-y-0 left-0 z-40 h-screen w-64 shrink-0 bg-[#122D40] text-white flex-col lg:flex lg:sticky lg:top-0`} data-testid="admin-sidebar">
        <div className="px-5 py-5 border-b border-white/10 flex items-start justify-between">
          <div><div className="text-xl font-bold tracking-wide">TRELPNG</div><div className="text-xs mt-1 text-white/70">Staff workspace</div></div>
          <button type="button" aria-label="Close menu" onClick={() => setMobileOpen(false)} className="p-1 lg:hidden"><X className="w-5 h-5" /></button>
        </div>
        <nav aria-label="Staff menus" className="p-3 flex-1 min-h-0 overflow-y-auto">
          {groups.map((group) => (
            <div key={group.id} className="mb-3">
              <button type="button" onClick={() => setOpenGroups((open) => ({ ...open, [group.id]: !open[group.id] }))} aria-expanded={!!openGroups[group.id]} aria-controls={`menu-${group.id}`} data-testid={`sidebar-group-${group.id}`}
                className="w-full flex items-center justify-between gap-2 px-3 py-3 rounded-md text-xs font-semibold uppercase tracking-wide text-white/80 hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">
                <span className="text-left">{group.label}</span><ChevronDown aria-hidden="true" className={`w-4 h-4 shrink-0 transition-transform ${openGroups[group.id] ? "rotate-180" : ""}`} />
              </button>
              <div id={`menu-${group.id}`} hidden={!openGroups[group.id]} data-testid={`sidebar-group-${group.id}-items`} className="mt-1">
                {group.items.map((item) => (
                  <NavLink key={item.to} to={item.to} end={item.end} onClick={() => setMobileOpen(false)} data-testid={`sidebar-link-${item.to.slice(7).replaceAll("/", "-") || "dashboard"}`}
                    className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm mb-1 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400 ${isActive ? "bg-[#17648A] text-white" : "text-white/75 hover:bg-white/5 hover:text-white"}`}>
                    <item.icon aria-hidden="true" className="w-4 h-4 shrink-0" /><span>{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="min-h-[72px] bg-white border-b border-[#E5E7EB] px-4 sm:px-6 py-3 flex items-center gap-3">
          <button type="button" aria-label="Open staff menu" aria-expanded={mobileOpen} aria-controls="staff-navigation" onClick={() => setMobileOpen(true)} className="p-2 border rounded-md lg:hidden"><Menu className="w-5 h-5" /></button>
          <div className="text-sm font-semibold mr-auto">Staff workspace</div>
          <div className="text-right leading-tight min-w-0"><div className="text-sm font-semibold break-words">{user?.name}</div><div className="text-xs text-[#6B7280]">{user?.role?.replaceAll("_", " ")}</div></div>
          <button onClick={handleLogout} data-testid="admin-logout-btn" className="shrink-0 flex items-center gap-2 px-3 py-2 rounded-md border border-[#D1D5DB] bg-white hover:bg-[#F9FAFB] text-sm font-medium"><LogOut className="w-4 h-4" /> Sign out</button>
        </header>
        <main className="p-4 sm:p-6 overflow-x-auto" data-testid="admin-main"><Outlet /></main>
      </div>
    </div>
  );
}
