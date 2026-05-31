import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

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

interface ActivityItem {
  id: string;
  title: string;
  starts_at: string;
  duration_min: number;
  type: string;
  source: string;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const { id } = await params;
  const supabase = await createClient();

  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Verify project belongs to user
  const { data: project } = await supabase
    .from("projects")
    .select("id")
    .eq("id", id)
    .eq("user_id", user.id)
    .single();

  if (!project) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  // Fetch tasks
  const { data: tasks } = await supabase
    .from("tasks")
    .select("id, title, status, priority, deadline, created_at")
    .eq("project_id", id)
    .order("priority")
    .order("deadline", { ascending: true, nullsFirst: false })
    .limit(50);

  // Fetch notes (exclude aria_chat source, most recent 8)
  const { data: notes } = await supabase
    .from("notes")
    .select("id, content, tags, created_at")
    .eq("project_id", id)
    .neq("source", "aria_chat")
    .order("created_at", { ascending: false })
    .limit(8);

  // Fetch upcoming events for this project (today onwards, sorted ascending)
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  const { data: activityEvents } = await supabase
    .from("events")
    .select("id, title, starts_at, duration_min, type, source")
    .eq("project_id", id)
    .gte("starts_at", todayStart.toISOString())
    .order("starts_at", { ascending: true })
    .limit(50);

  const taskList: Task[] = (tasks ?? []) as Task[];
  const noteList: Note[] = (notes ?? []) as Note[];

  const sevenDaysFromNow = new Date();
  sevenDaysFromNow.setDate(sevenDaysFromNow.getDate() + 7);

  const byStatus = taskList.reduce<Record<string, number>>((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});

  const urgent = taskList
    .filter((t) => {
      const isHighPriority = t.priority <= 2;
      const isDeadlineSoon =
        t.deadline !== null && new Date(t.deadline) <= sevenDaysFromNow;
      return isHighPriority || isDeadlineSoon;
    })
    .slice(0, 3);

  const statusOrder: Record<string, number> = { pending: 0, in_progress: 1 };
  const sortedTasks = [...taskList].sort((a, b) => {
    const sa = statusOrder[a.status] ?? 2;
    const sb = statusOrder[b.status] ?? 2;
    return sa !== sb ? sa - sb : a.priority - b.priority;
  });

  return NextResponse.json({
    taskStats: {
      total: taskList.length,
      byStatus,
      urgent,
      all: sortedTasks,
    },
    notes: noteList,
    activity: (activityEvents ?? []) as ActivityItem[],
  });
}
