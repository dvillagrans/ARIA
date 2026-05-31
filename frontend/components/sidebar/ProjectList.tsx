"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { FolderOpen, X } from "lucide-react";
import { useRealtime } from "@/lib/hooks/use-realtime";
import EmptyState from "@/components/ui/EmptyState";

export interface Project {
  id: string;
  name: string;
  color: string;
}

interface Task {
  id: string;
  project_id: string;
  title: string;
  status: string;
  [key: string]: unknown;
}

interface ProjectListProps {
  projects: Project[];
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

export default function ProjectList({ projects }: ProjectListProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [taskCounts, setTaskCounts] = useState<Record<string, number>>({});
  const [showModal, setShowModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(COLORS[0]);
  const [creating, setCreating] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showModal) setTimeout(() => nameInputRef.current?.focus(), 50);
  }, [showModal]);

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
      setShowModal(false);
      setNewName("");
      setNewColor(COLORS[0]);
      router.refresh();
    } finally {
      setCreating(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleCreate();
    if (e.key === "Escape") setShowModal(false);
  }

  return (
    <>
      {/* "+" button row */}
      <div className="flex items-center justify-end px-4 mb-1">
        <button
          onClick={() => setShowModal(true)}
          className="text-[11px] text-text-muted hover:text-accent transition-colors px-1.5 py-0.5"
          title="New project"
        >
          + New
        </button>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="No projects"
          description="Create one to get started."
        />
      ) : (
        <ul className="space-y-0.5 px-2">
          {projects.map((project) => {
            const href = `/projects/${project.id}/chat`;
            const isActive = pathname === href;
            return (
              <li key={project.id}>
                <Link
                  href={href}
                  className={`flex items-center justify-between px-3 py-1.5 transition-opacity duration-100 ${
                    isActive ? "opacity-100" : "opacity-70 hover:opacity-100"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="w-1.5 h-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: project.color }}
                    />
                    <span className="text-[13px] text-text-primary truncate">{project.name}</span>
                  </div>
                  {(taskCounts[project.id] ?? 0) > 0 && (
                    <span className="ml-2 shrink-0 text-[11px] text-text-muted tabular-nums">
                      {taskCounts[project.id]}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}

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
              className="fixed left-4 top-1/3 -translate-y-1/2 w-64 bg-bg-surface border border-bg-elevated rounded-sm p-5 z-50 shadow-2xl"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold">New project</h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1 rounded-sm hover:bg-bg-elevated transition-colors"
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
                className="w-full rounded-sm border border-bg-elevated bg-bg-root px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent/50 mb-4"
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
                className="w-full rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {creating ? "Creating…" : "Create"}
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
