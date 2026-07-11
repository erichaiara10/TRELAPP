import React, { useEffect, useState } from "react";
import { api, formatError } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Trash2 } from "lucide-react";

const ROLES = ["system_admin","managing_director","sales_manager","sales_agent","leasing_agent","property_manager","marketing_officer"];

export default function Users() {
  const { user: me } = useAuth();
  const [items, setItems] = useState([]);
  const [n, setN] = useState({ email: "", password: "", name: "", role: "sales_agent" });
  const load = () => api.get("/users").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try { await api.post("/users", n); toast.success("User created"); setN({ email:"", password:"", name:"", role:"sales_agent" }); load(); }
    catch (err) { toast.error(formatError(err)); }
  };
  const del = async (id) => { if (!window.confirm("Delete?")) return; try { await api.delete(`/users/${id}`); load(); } catch(e){toast.error(formatError(e));} };

  return (
    <div>
      <h1 className="text-2xl font-semibold">User management</h1>
      {me?.role === "system_admin" && (
        <form onSubmit={create} className="mt-4 bg-white border border-border rounded-lg p-4 grid md:grid-cols-5 gap-2" data-testid="user-form">
          <input required placeholder="Name" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} data-testid="user-name" className="border border-border rounded px-3 py-2" />
          <input required type="email" placeholder="Email" value={n.email} onChange={(e) => setN({ ...n, email: e.target.value })} data-testid="user-email" className="border border-border rounded px-3 py-2" />
          <input required type="password" placeholder="Password" value={n.password} onChange={(e) => setN({ ...n, password: e.target.value })} data-testid="user-pwd" className="border border-border rounded px-3 py-2" />
          <select value={n.role} onChange={(e) => setN({ ...n, role: e.target.value })} data-testid="user-role" className="border border-border rounded px-3 py-2">
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <button data-testid="user-add" className="rounded-md bg-[#0F172A] text-white">Add user</button>
        </form>
      )}
      <div className="mt-4 bg-white rounded-lg border border-border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-sand-50 text-left text-xs uppercase text-muted-foreground">
            <tr><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Role</th><th className="p-3">Created</th><th></th></tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id} className="border-t border-border" data-testid={`user-row-${u.id}`}>
                <td className="p-3 font-medium">{u.name}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3"><span className="px-2 py-0.5 rounded-full text-xs bg-sand-100">{u.role}</span></td>
                <td className="p-3 text-xs text-muted-foreground">{(u.created_at||"").slice(0,10)}</td>
                <td className="p-3 text-right">{me?.role === "system_admin" && u.id !== me.id && <button onClick={() => del(u.id)} data-testid={`del-user-${u.id}`} className="text-destructive p-1"><Trash2 className="w-4 h-4" /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
