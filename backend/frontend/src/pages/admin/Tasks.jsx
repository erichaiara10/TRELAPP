import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Check } from "lucide-react";

export default function Tasks() {
  const [items, setItems] = useState([]);
  const [t, setT] = useState({ title: "", description: "", priority: "medium", due_date: "" });
  const load = useCallback(() => api.get("/tasks").then((r) => setItems(r.data)), []);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    await api.post("/tasks", t);
    toast.success("Task created"); setT({ title: "", description: "", priority: "medium", due_date: "" }); load();
  };
  const done = async (id) => { await api.put(`/tasks/${id}`, { status: "done" }); load(); };

  return (
    <div>
      <h1 className="text-2xl font-semibold">Tasks</h1>
      <form onSubmit={create} className="mt-4 bg-white border border-border rounded-lg p-4 grid md:grid-cols-5 gap-2" data-testid="task-form">
        <input required placeholder="Title" value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} data-testid="task-title" className="border border-border rounded px-3 py-2 md:col-span-2" />
        <input type="date" value={t.due_date} onChange={(e) => setT({ ...t, due_date: e.target.value })} data-testid="task-due" className="border border-border rounded px-3 py-2" />
        <select value={t.priority} onChange={(e) => setT({ ...t, priority: e.target.value })} data-testid="task-prio" className="border border-border rounded px-3 py-2">
          <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
        </select>
        <button data-testid="task-add" className="rounded-md bg-[#0F172A] text-white flex items-center justify-center gap-1"><Plus className="w-4 h-4" /> Add task</button>
      </form>
      <div className="mt-4 space-y-2">
        {items.map((i) => (
          <div key={i.id} className="bg-white rounded-lg border border-border p-3 flex items-center gap-3" data-testid={`task-${i.id}`}>
            <button onClick={() => done(i.id)} className={`w-6 h-6 rounded border-2 flex items-center justify-center ${i.status==='done'?"bg-pine-500 border-pine-500 text-white":"border-border"}`} data-testid={`task-done-${i.id}`}>{i.status==='done' && <Check className="w-4 h-4" />}</button>
            <div className="flex-1">
              <div className={`text-sm font-medium ${i.status==='done'?"line-through text-muted-foreground":""}`}>{i.title}</div>
              <div className="text-xs text-muted-foreground">{i.due_date || "no due date"} · {i.priority}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
