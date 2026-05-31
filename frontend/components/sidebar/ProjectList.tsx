"use client";

import { useEffect, useState } from "react";
import { FolderOpen } from "lucide-react";
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

export default function ProjectList({ projects }: ProjectListProps) {
  const [taskCounts, setTaskCounts] = useState<Record<string, number>>({});

  const filters = projects.map((p) => ({
    table: "tasks",
    filter: `project_id=eq.${p.id}`,
  }));

  useRealtime<Task>(filters, (table, eventType, row) => {
    if (table !== "tasks") return;
    setTaskCounts((prev) => {
      const projectId = row.project_id;
      const current = prev[projectId] ?? 0;
      if (eventType === "INSERT") {
        return { ...prev, [projectId]: current + 1 };
      }
      if (eventType === "DELETE") {
        return { ...prev, [projectId]: Math.max(0, current - 1) };
      }
      return prev;
    });
  });

  if (projects.length === 0) {
    return (
      <EmptyState
        icon={FolderOpen}
        title="No projects yet"
        description="Create projects to organize your tasks."
      />
    );
  }

  return (
    <ul className="space-y-0.5 px-2">
      {projects.map((project) => (
        <li key={project.id}>
          <div className="flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-bg-elevated cursor-pointer transition-colors group">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: project.color }}
              />
              <span className="text-sm text-text-secondary truncate group-hover:text-text-primary transition-colors">
                {project.name}
              </span>
            </div>
            {(taskCounts[project.id] ?? 0) > 0 && (
              <span className="ml-2 shrink-0 text-[10px] bg-accent/20 text-accent rounded-full px-1.5 py-0.5 font-medium leading-none">
                {taskCounts[project.id]}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
