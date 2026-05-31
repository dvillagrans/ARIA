"use client";

import { useEffect, useState } from "react";
import { ChevronRight, FileText, GitBranch, CheckSquare, Clock, Activity, FolderOpen } from "lucide-react";
import GitHubRepoPanel from "./GitHubRepoPanel";

interface Task {
  id: string;
  title: string;
  status: string;
  priority: number;
  deadline: string | null;
  created_at: string;
}

interface Note {
  id: string;
  content: string;
  tags: string[] | null;
  created_at: string;
}

interface TaskStats {
  total: number;
  byStatus: Record<string, number>;
  urgent: Task[];
}

interface ActivityItem {
  id: string;
  title: string;
  starts_at: string;
  type: string;
  source: string;
}

interface PanelData {
  taskStats: TaskStats;
  notes: Note[];
  activity: ActivityItem[];
}

interface SectionCollapse {
  overview: boolean;
  tasks: boolean;
  notes: boolean;
  repository: boolean;
  activity: boolean;
  documents: boolean;
}

interface Props {
  projectId: string;
  projectName: string;
  projectColor: string;
  projectContext: string | null;
  projectGithubRepo: string | null;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays === -1) return "Yesterday";
  if (diffDays > 0 && diffDays < 7) return `in ${diffDays}d`;
  if (diffDays < 0 && diffDays > -7) return `${Math.abs(diffDays)}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function statusBadgeClass(status: string): string {
  if (status === "pending") return "bg-accent/15 text-accent border-accent/20";
  if (status === "in_progress") return "bg-accent/10 text-accent/80 border-accent/15";
  return "bg-bg-elevated text-text-muted border-border-subtle";
}

interface SectionProps {
  id: keyof SectionCollapse;
  label: string;
  icon: React.ElementType;
  collapsed: boolean;
  onToggle: (id: keyof SectionCollapse) => void;
  noPadding?: boolean;
  children: React.ReactNode;
}

function Section({ id, label, icon: Icon, collapsed, onToggle, noPadding, children }: SectionProps) {
  return (
    <div>
      <button
        onClick={() => onToggle(id)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-bg-elevated transition-colors"
      >
        <div className="flex items-center gap-1.5">
          <Icon className="h-3 w-3 text-text-muted" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-text-muted">{label}</span>
        </div>
        <ChevronRight
          className={`h-3 w-3 text-text-muted transition-transform ${collapsed ? "" : "rotate-90"}`}
        />
      </button>
      {!collapsed && (
        noPadding ? (
          <div className="overflow-hidden">{children}</div>
        ) : (
          <div className="px-3 pb-2">{children}</div>
        )
      )}
    </div>
  );
}

export default function InfoSidePanel({
  projectId,
  projectName,
  projectColor,
  projectContext,
  projectGithubRepo,
}: Props) {
  const sectionsKey = "aria-panel-sections-" + projectId;

  const [sectionCollapse, setSectionCollapse] = useState<SectionCollapse>({
    overview: false,
    tasks: false,
    notes: false,
    repository: false,
    activity: false,
    documents: false,
  });

  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());

  useEffect(() => {
    try {
      const stored = localStorage.getItem(sectionsKey);
      if (stored) {
        setSectionCollapse((prev) => ({ ...prev, ...JSON.parse(stored) }));
      }
    } catch {
      // ignore parse errors
    }
  }, [sectionsKey]);

  useEffect(() => {
    setLoading(true);
    fetch("/api/projects/" + projectId + "/panel")
      .then(async (res) => {
        if (!res.ok) return;
        const json = await res.json();
        setPanelData(json as PanelData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  function toggleSection(id: keyof SectionCollapse) {
    setSectionCollapse((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      try {
        localStorage.setItem(sectionsKey, JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  }

  function toggleNote(noteId: string) {
    setExpandedNotes((prev) => {
      const next = new Set(prev);
      if (next.has(noteId)) next.delete(noteId);
      else next.add(noteId);
      return next;
    });
  }

  const taskStats = panelData?.taskStats;
  const notes = panelData?.notes ?? [];
  const activity = panelData?.activity ?? [];

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin bg-bg-root">
      {/* Panel header */}
      <div className="shrink-0 flex items-center gap-2 px-3 h-10 border-b border-[#27272A] bg-bg-surface/50 sticky top-0 z-10">
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ backgroundColor: projectColor }}
        />
        <span className="text-xs font-medium text-text-secondary truncate">{projectName}</span>
      </div>

      {/* Sections */}
      <div className="flex flex-col divide-y divide-[#27272A]">
        {/* Overview */}
        <Section
          id="overview"
          label="Overview"
          icon={FileText}
          collapsed={sectionCollapse.overview}
          onToggle={toggleSection}
        >
          <div className="space-y-1.5 pt-0.5">
            {projectContext ? (
              <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">
                {projectContext}
              </p>
            ) : (
              <p className="text-xs text-text-muted italic">
                No description yet. Add one in the Info tab.
              </p>
            )}
          </div>
        </Section>

        {/* Tasks */}
        <Section
          id="tasks"
          label={`Tasks${taskStats ? ` · ${taskStats.total}` : ""}`}
          icon={CheckSquare}
          collapsed={sectionCollapse.tasks}
          onToggle={toggleSection}
        >
          {loading ? (
            <div className="space-y-1.5 pt-0.5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />
              ))}
            </div>
          ) : !taskStats || taskStats.total === 0 ? (
            <p className="text-xs text-text-muted pt-0.5">No tasks for this project.</p>
          ) : (
            <div className="pt-0.5 space-y-2">
              {/* Status pills */}
              <div className="flex flex-wrap gap-1">
                {Object.entries(taskStats.byStatus).map(([status, count]) => (
                  <span
                    key={status}
                    className={`px-1.5 py-0.5 text-[10px] rounded-sm border ${statusBadgeClass(status)}`}
                  >
                    {status} · {count}
                  </span>
                ))}
              </div>

              {/* Urgent tasks */}
              {taskStats.urgent.length > 0 && (
                <div className="border border-border-subtle rounded-sm overflow-hidden">
                  <div className="px-2.5 py-1.5 bg-bg-elevated text-[10px] font-mono uppercase tracking-widest text-text-muted flex items-center gap-1.5">
                    <Clock className="h-3 w-3" />
                    Urgent
                  </div>
                  {taskStats.urgent.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-start gap-2 px-2.5 py-1.5 border-t border-border-subtle"
                    >
                      <span
                        className={`shrink-0 text-[10px] px-1 rounded-sm ${
                          task.priority <= 2
                            ? "bg-red-950 text-red-400"
                            : "bg-bg-elevated text-text-muted"
                        }`}
                      >
                        P{task.priority}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-text-primary truncate">{task.title}</p>
                        {task.deadline && (
                          <p className="text-[10px] text-text-muted">
                            {new Date(task.deadline).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                            })}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Section>

        {/* Notes */}
        <Section
          id="notes"
          label="Notes"
          icon={FileText}
          collapsed={sectionCollapse.notes}
          onToggle={toggleSection}
        >
          {loading ? (
            <div className="space-y-1.5 pt-0.5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />
              ))}
            </div>
          ) : notes.length === 0 ? (
            <p className="text-xs text-text-muted pt-0.5">No notes yet.</p>
          ) : (
            <div className="pt-0.5">
              {notes.map((note) => (
                <div
                  key={note.id}
                  className="text-xs border border-border-subtle rounded-sm overflow-hidden mb-1.5"
                >
                  <button
                    onClick={() => toggleNote(note.id)}
                    className="w-full text-left px-2.5 py-1.5 hover:bg-bg-elevated transition-colors"
                  >
                    <p className="text-text-secondary truncate">{note.content.slice(0, 100)}</p>
                    <p className="text-[10px] text-text-muted mt-0.5">{formatDate(note.created_at)}</p>
                  </button>
                  {expandedNotes.has(note.id) && (
                    <div className="px-2.5 pb-2 border-t border-border-subtle">
                      <p className="text-text-secondary text-xs leading-relaxed whitespace-pre-wrap">
                        {note.content}
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Repository */}
        <Section
          id="repository"
          label="Repository"
          icon={GitBranch}
          collapsed={sectionCollapse.repository}
          onToggle={toggleSection}
          noPadding={!!projectGithubRepo}
        >
          {projectGithubRepo ? (
            <GitHubRepoPanel repo={projectGithubRepo} className="flex flex-col gap-3" />
          ) : (
            <p className="text-xs text-text-muted pt-0.5">
              No repository linked. Add one in the{" "}
              <span className="text-accent">Info</span> tab.
            </p>
          )}
        </Section>

        {/* Activity */}
        <Section
          id="activity"
          label="Activity"
          icon={Activity}
          collapsed={sectionCollapse.activity}
          onToggle={toggleSection}
        >
          {loading ? (
            <div className="space-y-1.5 pt-0.5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />
              ))}
            </div>
          ) : activity.length === 0 ? (
            <p className="text-xs text-text-muted pt-0.5">No recent activity.</p>
          ) : (
            <div className="pt-0.5 flex flex-col gap-0">
              {activity.map((item, i) => (
                <div
                  key={item.id}
                  className="flex items-start gap-2.5 py-1.5 relative"
                >
                  {/* Timeline line */}
                  {i < activity.length - 1 && (
                    <div className="absolute left-[5px] top-4 bottom-0 w-px bg-border-subtle" />
                  )}
                  {/* Dot */}
                  <div className="w-2.5 h-2.5 rounded-full border border-border-subtle bg-bg-elevated shrink-0 mt-0.5 z-10" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-text-primary truncate">{item.title}</p>
                    <p className="text-[10px] text-text-muted">{formatDateTime(item.starts_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Documents */}
        <Section
          id="documents"
          label="Documents"
          icon={FolderOpen}
          collapsed={sectionCollapse.documents}
          onToggle={toggleSection}
        >
          <p className="text-xs text-text-muted pt-0.5">
            No documents yet.{" "}
            <span className="text-text-secondary">Upload files and PDFs via chat.</span>
          </p>
        </Section>
      </div>
    </div>
  );
}
