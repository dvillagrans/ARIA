"use client";

/**
 * ProjectList — lists active projects with task count badges.
 *
 * Subscribes to a per-project Realtime channel for tasks (INSERT/UPDATE/DELETE).
 * Tasks from a different project do not affect this list.
 *
 * Spec §7: per-project Realtime channel for tasks.
 * ADR-06.
 */

import { useEffect, useState } from "react";
import { useRealtime } from "@/lib/hooks/use-realtime";

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
}

interface ProjectListProps {
  projects: Project[];
}

export default function ProjectList({ projects }: ProjectListProps) {
  const [taskCounts, setTaskCounts] = useState<Record<string, number>>({});

  // Build one Realtime filter per project for tasks.
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
      <p className="text-xs text-gray-500 px-3 py-2">No projects yet.</p>
    );
  }

  return (
    <ul className="space-y-1">
      {projects.map((project) => (
        <li key={project.id}>
          <div className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-800 cursor-pointer transition-colors">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: project.color }}
              />
              <span className="text-sm text-gray-200 truncate">
                {project.name}
              </span>
            </div>
            {(taskCounts[project.id] ?? 0) > 0 && (
              <span className="ml-2 shrink-0 text-xs bg-indigo-600 text-white rounded-full px-1.5 py-0.5 leading-none">
                {taskCounts[project.id]}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
