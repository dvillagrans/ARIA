"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { FolderKanban, FolderOpen, Plus, X } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { useRealtime } from "@/lib/hooks/use-realtime";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";

interface Project {
  id: string;
  name: string;
  color: string;
  is_active: boolean;
}

interface Task {
  id: string;
  project_id: string;
  title: string;
  status: string;
  [key: string]: unknown;
}

const COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#ec4899",
  "#ef4444",
  "#f59e0b",
  "#10b981",
  "#06b6d4",
  "#64748b",
];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [taskCounts, setTaskCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(COLORS[0]);
  const [creating, setCreating] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showModal) setTimeout(() => nameInputRef.current?.focus(), 50);
  }, [showModal]);

  useEffect(() => {
    async function loadProjects() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) return;

      const { data } = await supabase
        .from("projects")
        .select("id, name, color, is_active")
        .eq("user_id", user.id)
        .eq("is_active", true)
        .neq("name", "Personal")
        .order("name", { ascending: true });

      setProjects((data as Project[]) ?? []);
      setLoading(false);
    }
    loadProjects();
  }, []);

  const filters = projects.map((p) => ({
    table: "tasks",
    filter: `project_id=eq.${p.id}`,
  }));

  useRealtime<Task>(filters, (table, eventType, row) => {
    if (table !== "tasks") return;
    setTaskCounts((prev) => {
      const projectId = row.project_id;
      const current = prev[projectId] ?? 0;
      if (eventType === "INSERT") return { ...prev, [projectId]: current + 1 };
      if (eventType === "DELETE") return { ...prev, [projectId]: Math.max(0, current - 1) };
      return prev;
    });
  });

  async function handleCreate() {
    if (!newName.trim() || creating) return;
    setCreating(true);
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), color: newColor }),
      });
      if (!res.ok) return;
      const project: Project = await res.json();
      setProjects((prev) =>
        [...prev, { ...project, is_active: true }].sort((a, b) =>
          a.name.localeCompare(b.name)
        )
      );
      setShowModal(false);
      setNewName("");
      setNewColor(COLORS[0]);
      // Refresh sidebar (server component) with new project.
      router.refresh();
    } finally {
      setCreating(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleCreate();
    if (e.key === "Escape") setShowModal(false);
  }

  if (loading) {
    return (
      <main className="flex flex-col h-full bg-bg-root">
        <Header onNew={() => setShowModal(true)} />
        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3">
            {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
          </div>
        </div>
      </main>
    );
  }

  return (
    <>
      <main className="flex flex-col h-full bg-bg-root">
        <Header count={projects.length} onNew={() => setShowModal(true)} />

        {projects.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState
              icon={FolderOpen}
              title="No projects yet"
              description="Create a project to get started organizing your tasks."
            />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
            <motion.ul variants={container} initial="hidden" animate="show" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3">
              {projects.map((project) => (
                <motion.li key={project.id} variants={item}>
                  <button
                    onClick={() => router.push(`/projects/${project.id}/chat`)}
                    className="w-full text-left bg-bg-surface rounded-xl border border-border-subtle hover:border-border-strong p-4 hover:bg-bg-surface transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 min-w-0">
                        <span
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: project.color }}
                        />
                        <span className="text-sm font-medium text-text-primary truncate">
                          {project.name}
                        </span>
                      </div>
                      {(taskCounts[project.id] ?? 0) > 0 && (
                        <span className="ml-3 shrink-0 text-xs bg-accent/20 text-accent rounded-full px-2 py-0.5 font-medium tabular-nums">
                          {taskCounts[project.id]}
                        </span>
                      )}
                    </div>
                  </button>
                </motion.li>
              ))}
            </motion.ul>
          </div>
        )}
      </main>

      {/* New Project Modal */}
      <AnimatePresence>
        {showModal && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowModal(false)}
              className="fixed inset-0 bg-black/60 z-40"
            />
            <motion.div
              key="modal"
              initial={{ opacity: 0, scale: 0.95, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 8 }}
              transition={{ type: "spring", duration: 0.25 }}
              className="fixed inset-x-4 top-1/3 -translate-y-1/2 md:inset-auto md:left-1/2 md:-translate-x-1/2 md:w-80 bg-bg-surface border border-bg-elevated rounded-2xl p-5 z-50 shadow-2xl"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold">New project</h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1 rounded-lg hover:bg-bg-elevated transition-colors"
                >
                  <X className="h-4 w-4 text-text-muted" />
                </button>
              </div>

              <input
                ref={nameInputRef}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Project name"
                className="w-full rounded-lg border border-bg-elevated bg-bg-root px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent/50 mb-4"
              />

              <p className="text-xs uppercase tracking-widest text-text-muted mb-2">Color</p>
              <div className="flex gap-2 flex-wrap mb-5">
                {COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setNewColor(color)}
                    className={`w-9 h-9 rounded-full transition-all ${
                      newColor === color
                        ? "ring-2 ring-text-primary ring-offset-2 ring-offset-bg-surface"
                        : "hover:scale-110"
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>

              <button
                onClick={handleCreate}
                disabled={!newName.trim() || creating}
                className="w-full rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {creating ? "Creating…" : "Create project"}
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

function Header({ count, onNew }: { count?: number; onNew: () => void }) {
  return (
    <header className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm">
      <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center shrink-0">
        <FolderKanban className="h-4 w-4 text-accent" strokeWidth={1.5} />
      </div>
      <div className="flex-1 min-w-0">
        <h1 className="text-sm font-semibold">Projects</h1>
        {count != null && (
          <p className="text-xs text-text-muted">{count} active</p>
        )}
      </div>
      <button
        onClick={onNew}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent/15 hover:bg-accent/25 text-accent text-xs font-medium transition-colors"
      >
        <Plus className="h-3.5 w-3.5" />
        New
      </button>
    </header>
  );
}
