import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, Building2, Users, Inbox, ClipboardList, Target, Calendar, ListChecks, KanbanSquare, UserCog, FileText, BarChart3, MapPin, LogOut } from "lucide-react";
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
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const handleLogout = async () => { await logout(); nav("/admin/login"); };

  return (
    <div className="min-h-screen flex bg-[#F3F4F6] text-[#111827]" style={{ fontFamily: "Outfit, sans-serif" }}>
      <aside className="w-64 shrink-0 bg-[#0F172A] text-white flex flex-col" data-testid="admin-sidebar">
        <div className="px-5 py-5 border-b border-white/10">
          <div className="text-sm uppercase tracking-[0.3em] text-white/50">TREL</div>
          <div className="font-serif text-xl mt-1">Operations</div>
        </div>
        <nav className="p-3 flex-1 overflow-y-auto">
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
        </nav>
        <div className="p-4 border-t border-white/10 text-sm">
          <div className="font-medium">{user?.name}</div>
          <div className="text-xs text-white/60 mb-3">{user?.role}</div>
          <button onClick={handleLogout} data-testid="admin-logout-btn"
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-white/10 hover:bg-white/20">
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-6 overflow-y-auto" data-testid="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
