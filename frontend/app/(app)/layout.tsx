import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import Sidebar from "@/components/sidebar/Sidebar";
import type { CalendarEvent } from "@/components/sidebar/EventList";
import type { Reminder } from "@/components/sidebar/ReminderList";
import type { Project } from "@/components/sidebar/ProjectList";

/**
 * Protected route group layout — Phase 3 update.
 *
 * Phase 1 behavior preserved:
 * - Runs server-side before any child page renders.
 * - If no authenticated session exists, redirects to /login.
 *
 * Phase 3 additions:
 * - Fetches initialEvents (next 7 days) and initialReminders (pending)
 *   concurrently via SSR before rendering.
 * - Passes both as props to Sidebar for zero-flash first paint.
 * - Fetches active projects for Sidebar.
 * - Query failures return empty arrays — layout never breaks.
 *
 * Spec §sidebar-ssr: AppLayout SSR Data Fetch.
 */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Compute date range for events (today to +7 days).
  const today = new Date();
  const sevenDaysFromNow = new Date(today);
  sevenDaysFromNow.setDate(today.getDate() + 7);
  const todayIso = today.toISOString();
  const sevenDaysIso = sevenDaysFromNow.toISOString();

  // Run three concurrent SSR queries.
  const [eventsResult, remindersResult, projectsResult] = await Promise.all([
    supabase
      .from("events")
      .select("id, title, starts_at, duration_min, type")
      .eq("user_id", user.id)
      .gte("starts_at", todayIso)
      .lte("starts_at", sevenDaysIso)
      .order("starts_at", { ascending: true })
      .limit(20),
    supabase
      .from("reminders")
      .select("id, title, due_at, is_done, amount, currency")
      .eq("user_id", user.id)
      .eq("is_done", false)
      .order("due_at", { ascending: true })
      .limit(20),
    supabase
      .from("projects")
      .select("id, name, color, is_active")
      .eq("user_id", user.id)
      .eq("is_active", true)
      .order("name", { ascending: true }),
  ]);

  // Graceful fallback to empty arrays on query failure.
  const initialEvents: CalendarEvent[] = (eventsResult.data ?? []) as CalendarEvent[];
  const initialReminders: Reminder[] = (remindersResult.data ?? []) as Reminder[];
  const projects: Project[] = (projectsResult.data ?? []) as Project[];

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        userId={user.id}
        projects={projects}
        initialEvents={initialEvents}
        initialReminders={initialReminders}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
