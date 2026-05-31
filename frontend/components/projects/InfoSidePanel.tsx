"use client";

import { useEffect, useState } from "react";
import { ChevronRight, FileText, GitBranch, CheckSquare, Activity, FolderOpen } from "lucide-react";
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
  all: Task[];
}

interface ActivityItem {
  id: string;
  title: string;
  starts_at: string;
  duration_min: number;
  type: string;
  source: string;
}

interface DocumentItem {
  id: string;
  name: string;
  mime_type: string | null;
  size_bytes: number | null;
  status: string;
  created_at: string;
}

interface PanelData {
  taskStats: TaskStats;
  notes: Note[];
  documents: DocumentItem[];
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

// ── Date helpers ─────────────────────────────────────────────────────────────

function startOfDay(d: Date): Date {
  const s = new Date(d);
  s.setHours(0, 0, 0, 0);
  return s;
}

function addDays(d: Date, n: number): Date {
  const s = new Date(d);
  s.setDate(s.getDate() + n);
  return s;
}

function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d
    .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })
    .toLowerCase()
    .replace(/\s/, "");
}

function formatDuration(mins: number): string {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface DayGroup {
  key: string;
  weekday: string;    // "WEDNESDAY"
  dateLabel: string;  // "Jun 4"
  events: ActivityItem[];
}

function groupByDay(events: ActivityItem[]): DayGroup[] {
  const map = new Map<string, ActivityItem[]>();
  for (const e of events) {
    const k = localDayKey(new Date(e.starts_at));
    if (!map.has(k)) map.set(k, []);
    map.get(k)!.push(e);
  }
  return [...map.entries()].map(([key, evts]) => {
    const d = new Date(key + "T12:00:00");
    return {
      key,
      weekday: d.toLocaleDateString("en-US", { weekday: "long" }).toUpperCase(),
      dateLabel: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      events: evts,
    };
  });
}

function bucketActivity(events: ActivityItem[]) {
  const now = new Date();
  const todayStart = startOfDay(now);
  const tomorrowStart = addDays(todayStart, 1);
  const dayAfterTomorrow = addDays(todayStart, 2);
  const weekEnd = addDays(todayStart, 7);

  const today: ActivityItem[] = [];
  const tomorrow: ActivityItem[] = [];
  const thisWeekRaw: ActivityItem[] = [];
  const beyondRaw: ActivityItem[] = [];

  for (const e of events) {
    const d = new Date(e.starts_at);
    if (d < tomorrowStart) today.push(e);
    else if (d < dayAfterTomorrow) tomorrow.push(e);
    else if (d < weekEnd) thisWeekRaw.push(e);
    else beyondRaw.push(e);
  }

  return {
    today,
    tomorrow,
    thisWeek: groupByDay(thisWeekRaw),
    beyond: groupByDay(beyondRaw),
  };
}

// ── Sub-components ────────────────────────────────────────────────────────────

function EventRow({ event }: { event: ActivityItem }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 border-t border-[#27272A]">
      <span className="text-[10px] font-mono text-text-muted shrink-0 w-14 text-right">
        {formatTime(event.starts_at)}
      </span>
      <span className="text-xs text-text-primary truncate flex-1">{event.title}</span>
      <span className="text-[10px] text-text-muted shrink-0">
        {formatDuration(event.duration_min)}
      </span>
    </div>
  );
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

// ── Main component ────────────────────────────────────────────────────────────

export default function InfoSidePanel({
  projectId,
  projectName,
  projectColor,
  projectContext,
  projectGithubRepo,
}: Props) {
  const sectionsKey = "aria-panel-sections-" + projectId;
  const activityKey = "aria-activity-" + projectId;

  const [sectionCollapse, setSectionCollapse] = useState<SectionCollapse>({
    overview: false,
    tasks: false,
    notes: false,
    repository: false,
    activity: false,
    documents: false,
  });

  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set());
  const [showBeyond, setShowBeyond] = useState(false);

  const [panelData, setPanelData] = useState<PanelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());

  useEffect(() => {
    try {
      const stored = localStorage.getItem(sectionsKey);
      if (stored) setSectionCollapse((prev) => ({ ...prev, ...JSON.parse(stored) }));
    } catch {}
  }, [sectionsKey]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(activityKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed.days)) setExpandedDays(new Set(parsed.days as string[]));
        if (typeof parsed.beyond === "boolean") setShowBeyond(parsed.beyond);
      }
    } catch {}
  }, [activityKey]);

  useEffect(() => {
    setLoading(true);
    fetch("/api/projects/" + projectId + "/panel")
      .then(async (res) => {
        if (!res.ok) return;
        setPanelData((await res.json()) as PanelData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  function toggleSection(id: keyof SectionCollapse) {
    setSectionCollapse((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      try { localStorage.setItem(sectionsKey, JSON.stringify(next)); } catch {}
      return next;
    });
  }

  function toggleDay(dayKey: string) {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(dayKey)) next.delete(dayKey);
      else next.add(dayKey);
      try {
        localStorage.setItem(activityKey, JSON.stringify({ days: [...next], beyond: showBeyond }));
      } catch {}
      return next;
    });
  }

  function handleToggleBeyond() {
    setShowBeyond((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(activityKey, JSON.stringify({ days: [...expandedDays], beyond: next }));
      } catch {}
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
  const documents = panelData?.documents ?? [];
  const activity = panelData?.activity ?? [];

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin bg-bg-root">
      {/* Panel header */}
      <div className="shrink-0 flex items-center gap-2 px-3 h-10 border-b border-[#27272A] bg-bg-surface/50 sticky top-0 z-10">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: projectColor }} />
        <span className="text-xs font-medium text-text-secondary truncate">{projectName}</span>
      </div>

      {/* Sections */}
      <div className="flex flex-col divide-y divide-[#27272A]">

        {/* Overview — only show if has content */}
        {(projectContext || !loading) && (
          <Section id="overview" label="Overview" icon={FileText} collapsed={projectContext ? sectionCollapse.overview : true} onToggle={toggleSection}>
            {projectContext ? (
              <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap pt-0.5">{projectContext}</p>
            ) : (
              <p className="text-xs text-text-muted italic pt-0.5">No description yet. Add one in the Info tab.</p>
            )}
          </Section>
        )}

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
              {[0, 1, 2].map((i) => <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />)}
            </div>
          ) : !taskStats || taskStats.total === 0 ? (
            <p className="text-xs text-text-muted pt-0.5">No tasks for this project.</p>
          ) : (
            <div className="pt-0.5">
              <div className="border border-border-subtle rounded-sm overflow-hidden">
                {taskStats.all.map((task, i) => {
                  const isDone = task.status === "done" || task.status === "completed";
                  return (
                    <div
                      key={task.id}
                      className={`flex items-start gap-2 px-2.5 py-1.5 ${i > 0 ? "border-t border-border-subtle" : ""} ${isDone ? "opacity-40" : ""}`}
                    >
                      <span className={`shrink-0 text-[10px] px-1 rounded-sm mt-0.5 ${task.priority <= 2 ? "bg-red-950 text-red-400" : "bg-bg-elevated text-text-muted"}`}>
                        P{task.priority}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className={`text-xs truncate ${isDone ? "line-through text-text-muted" : "text-text-primary"}`}>
                          {task.title}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={`text-[10px] ${statusBadgeClass(task.status).includes("accent") ? "text-accent" : "text-text-muted"}`}>
                            {task.status}
                          </span>
                          {task.deadline && (
                            <span className="text-[10px] text-text-muted">
                              {new Date(task.deadline).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Section>

        {/* Notes — auto-collapse when empty */}
        <Section id="notes" label="Notes" icon={FileText} collapsed={notes.length === 0 ? true : sectionCollapse.notes} onToggle={toggleSection}>
          {loading ? (
            <div className="space-y-1.5 pt-0.5">
              {[0, 1, 2].map((i) => <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />)}
            </div>
          ) : notes.length === 0 ? (
            <p className="text-xs text-text-muted pt-0.5">No notes yet.</p>
          ) : (
            <div className="pt-0.5">
              {notes.map((note) => (
                <div key={note.id} className="text-xs border border-border-subtle rounded-sm overflow-hidden mb-1.5">
                  <button
                    onClick={() => toggleNote(note.id)}
                    className="w-full text-left px-2.5 py-1.5 hover:bg-bg-elevated transition-colors"
                  >
                    <p className="text-text-secondary truncate">{note.content.slice(0, 100)}</p>
                    <p className="text-[10px] text-text-muted mt-0.5">{formatDate(note.created_at)}</p>
                  </button>
                  {expandedNotes.has(note.id) && (
                    <div className="px-2.5 pb-2 border-t border-border-subtle">
                      <p className="text-text-secondary text-xs leading-relaxed whitespace-pre-wrap">{note.content}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Repository — auto-collapse when no repo */}
        <Section
          id="repository"
          label="Repository"
          icon={GitBranch}
          collapsed={projectGithubRepo ? sectionCollapse.repository : true}
          onToggle={toggleSection}
          noPadding={!!projectGithubRepo}
        >
          {projectGithubRepo ? (
            <GitHubRepoPanel repo={projectGithubRepo} className="flex flex-col gap-3" />
          ) : (
            <p className="text-xs text-text-muted pt-0.5">
              No repository linked. Add one in the <span className="text-accent">Info</span> tab.
            </p>
          )}
        </Section>

        {/* Activity — auto-collapse when empty */}
        <Section
          id="activity"
          label="Activity"
          icon={Activity}
          collapsed={activity.length === 0 ? true : sectionCollapse.activity}
          onToggle={toggleSection}
          noPadding
        >
          {loading ? (
            <div className="px-3 pb-2 pt-0.5 space-y-1.5">
              {[0, 1, 2].map((i) => <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />)}
            </div>
          ) : activity.length === 0 ? (
            <p className="px-3 pb-2 pt-0.5 text-xs text-text-muted">No upcoming events.</p>
          ) : (() => {
            const { today: todayEvts, tomorrow: tomorrowEvts, thisWeek, beyond } = bucketActivity(activity);
            const hasBeyond = beyond.length > 0;
            const beyondDayCount = beyond.length;

            return (
              <div className="pb-1">
                {/* Today — always expanded */}
                {todayEvts.length > 0 && (
                  <div>
                    <div className="px-3 py-1.5 border-t border-[#27272A]">
                      <span className="text-[10px] font-mono uppercase tracking-widest text-text-muted">
                        Today · {todayEvts.length}
                      </span>
                    </div>
                    {todayEvts.map((e) => <EventRow key={e.id} event={e} />)}
                  </div>
                )}

                {/* Tomorrow — always expanded */}
                {tomorrowEvts.length > 0 && (
                  <div>
                    <div className="px-3 py-1.5 border-t border-[#27272A]">
                      <span className="text-[10px] font-mono uppercase tracking-widest text-text-muted">
                        Tomorrow · {tomorrowEvts.length}
                      </span>
                    </div>
                    {tomorrowEvts.map((e) => <EventRow key={e.id} event={e} />)}
                  </div>
                )}

                {/* This week — per-day toggle, collapsed by default */}
                {thisWeek.map((day) => (
                  <div key={day.key}>
                    <button
                      onClick={() => toggleDay(day.key)}
                      className="w-full flex items-center justify-between px-3 py-1.5 border-t border-[#27272A] hover:bg-bg-elevated transition-colors"
                    >
                      <span className="text-[10px] font-mono uppercase tracking-widest text-text-muted">
                        {day.weekday} · {day.events.length}
                      </span>
                      <ChevronRight
                        className={`h-3 w-3 text-text-muted transition-transform ${expandedDays.has(day.key) ? "rotate-90" : ""}`}
                      />
                    </button>
                    {expandedDays.has(day.key) && day.events.map((e) => <EventRow key={e.id} event={e} />)}
                  </div>
                ))}

                {/* Beyond — hidden until clicked */}
                {hasBeyond && !showBeyond && (
                  <button
                    onClick={handleToggleBeyond}
                    className="w-full text-left px-3 py-2 border-t border-[#27272A] text-[10px] font-mono text-text-muted hover:text-text-secondary transition-colors"
                  >
                    show {beyondDayCount} more {beyondDayCount === 1 ? "day" : "days"}
                  </button>
                )}
                {showBeyond && beyond.map((day) => (
                  <div key={day.key}>
                    <div className="flex items-center justify-between px-3 py-1.5 border-t border-[#27272A]">
                      <span className="text-[10px] font-mono uppercase tracking-widest text-text-muted">
                        {day.weekday}
                        <span className="ml-1.5 normal-case">{day.dateLabel}</span>
                      </span>
                    </div>
                    {day.events.map((e) => <EventRow key={e.id} event={e} />)}
                  </div>
                ))}
              </div>
            );
          })()}
        </Section>

        {/* Documents */}
        <Section
          id="documents"
          label={`Documents${documents.length > 0 ? ` · ${documents.length}` : ""}`}
          icon={FolderOpen}
          collapsed={sectionCollapse.documents}
          onToggle={toggleSection}
        >
          {loading ? (
            <div className="space-y-1.5 pt-0.5">
              {[0, 1].map((i) => <div key={i} className="animate-pulse bg-bg-elevated h-3 rounded-sm" />)}
            </div>
          ) : documents.length === 0 ? (
            <p className="text-xs text-text-muted pt-0.5">
              No documents yet —{" "}
              <span className="text-text-secondary">attach files via the chat (PDF, TXT, MD).</span>
            </p>
          ) : (
            <div className="pt-0.5 flex flex-col gap-1">
              {documents.map((doc) => {
                const isPdf = doc.mime_type === "application/pdf" || doc.name.endsWith(".pdf");
                const sizeMb = doc.size_bytes ? (doc.size_bytes / 1024 / 1024).toFixed(1) : null;
                return (
                  <div
                    key={doc.id}
                    className="flex items-center gap-2 px-2.5 py-1.5 rounded-sm border border-border-subtle bg-bg-surface/50"
                  >
                    <span className="text-[10px] font-mono text-text-muted shrink-0 uppercase">
                      {isPdf ? "pdf" : doc.name.split(".").pop() ?? "txt"}
                    </span>
                    <span className="text-xs text-text-primary truncate flex-1">{doc.name}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {sizeMb && (
                        <span className="text-[10px] text-text-muted">{sizeMb}MB</span>
                      )}
                      <span
                        className={`text-[10px] px-1 rounded-sm ${
                          doc.status === "done"
                            ? "text-accent bg-accent/10"
                            : doc.status === "error"
                            ? "text-red-400 bg-red-950"
                            : "text-text-muted bg-bg-elevated"
                        }`}
                      >
                        {doc.status === "done" ? "indexed" : doc.status === "error" ? "error" : "…"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Section>

      </div>
    </div>
  );
}
