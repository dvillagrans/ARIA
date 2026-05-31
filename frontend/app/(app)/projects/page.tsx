"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FolderKanban, FolderOpen, Bot } from "lucide-react";
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

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [taskCounts, setTaskCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

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

  if (loading) {
    return (
      <main className="flex flex-col h-full bg-bg-root">
        <Header />
        <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </main>
    );
  }

  if (projects.length === 0) {
    return (
      <main className="flex flex-col h-full bg-bg-root">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <EmptyState
            icon={FolderOpen}
            title="No projects yet"
            description="Projects help you organize tasks and track progress. They'll appear here once created."
          />
        </div>
      </main>
    );
  }

  return (
    <main className="flex flex-col h-full bg-bg-root">
      <Header count={projects.length} />
      <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
        <motion.ul variants={container} initial="hidden" animate="show" className="space-y-2">
          {projects.map((project) => (
            <motion.li key={project.id} variants={item}>
              <div className="bg-bg-surface/60 rounded-xl border border-bg-elevated p-4 hover:bg-bg-surface transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className="w-3 h-3 rounded-full shrink-0 ring-2 ring-bg-root"
                      style={{ backgroundColor: project.color }}
                    />
                    <span className="text-sm font-medium text-text-primary truncate">
                      {project.name}
                    </span>
                  </div>
                  {(taskCounts[project.id] ?? 0) > 0 && (
                    <span className="ml-3 shrink-0 text-xs bg-accent/20 text-accent rounded-full px-2 py-0.5 font-medium">
                      {taskCounts[project.id]} task{(taskCounts[project.id] ?? 0) !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
              </div>
            </motion.li>
          ))}
        </motion.ul>
      </div>
    </main>
  );
}

function Header({ count }: { count?: number }) {
  return (
    <header className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm">
      <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center shrink-0">
        <FolderKanban className="h-4 w-4 text-accent" strokeWidth={1.5} />
      </div>
      <div className="flex-1 min-w-0">
        <h1 className="text-sm font-semibold">Projects</h1>
        {count != null && (
          <p className="text-[10px] text-text-muted">{count} active</p>
        )}
      </div>
    </header>
  );
}
