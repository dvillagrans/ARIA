import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import Sidebar from "@/components/sidebar/Sidebar";
import BottomNav from "@/components/navigation/BottomNav";
import type { CalendarEvent } from "@/components/sidebar/EventList";
import type { Reminder } from "@/components/sidebar/ReminderList";
import type { Project } from "@/components/sidebar/ProjectList";

/**
 * Protected route group layout — responsive mobile-first.
 *
 * Mobile (default): full-width content + BottomNav.
 * Desktop (md+): fixed sidebar (w-64) + content + no BottomNav.
 */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  // proxy.ts already validated the session with getUser(); read cookies locally
  // to avoid a second round-trip to Supabase Auth on every page load.
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const user = session?.user;

  if (!user) {
    redirect("/login");
  }

  const today = new Date();
  const sevenDaysFromNow = new Date(today);
  sevenDaysFromNow.setDate(today.getDate() + 7);
  const todayIso = today.toISOString();
  const sevenDaysIso = sevenDaysFromNow.toISOString();

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
      .select("id, title, due_at, is_done, amount, currency, calendar_event_id")
      .eq("user_id", user.id)
      .eq("is_done", false)
      .order("due_at", { ascending: true })
      .limit(20),
    supabase
      .from("projects")
      .select("id, name, color, is_active")
      .eq("user_id", user.id)
      .eq("is_active", true)
      .neq("name", "Personal")
      .order("name", { ascending: true }),
  ]);

  const initialEvents: CalendarEvent[] = (eventsResult.data ?? []) as CalendarEvent[];
  const initialReminders: Reminder[] = (remindersResult.data ?? []) as Reminder[];
  const projects: Project[] = (projectsResult.data ?? []) as Project[];

  return (
    <div className="flex h-dvh overflow-hidden bg-bg-root">
      {/* Sidebar — desktop only */}
      <div className="hidden md:block shrink-0">
        <Sidebar
          userId={user.id}
          userEmail={user.email ?? ""}
          projects={projects}
          initialEvents={initialEvents}
          initialReminders={initialReminders}
        />
      </div>

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden pb-nav md:pb-0">
        {children}
      </div>

      {/* Bottom nav — mobile only */}
      <div className="md:hidden">
        <BottomNav />
      </div>
    </div>
  );
}
