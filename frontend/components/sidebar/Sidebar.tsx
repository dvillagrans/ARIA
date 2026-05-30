"use client";

/**
 * Sidebar — composes ProjectList, EventList, and ReminderList.
 *
 * All three lists update in real-time via Supabase Realtime channels.
 * Spec §7: sidebar renders all three lists.
 */

import ProjectList, { Project } from "./ProjectList";
import EventList, { CalendarEvent } from "./EventList";
import ReminderList, { Reminder } from "./ReminderList";

interface SidebarProps {
  userId: string;
  projects: Project[];
  initialEvents?: CalendarEvent[];
  initialReminders?: Reminder[];
}

export default function Sidebar({
  userId,
  projects,
  initialEvents = [],
  initialReminders = [],
}: SidebarProps) {
  return (
    <aside className="flex flex-col w-64 shrink-0 bg-gray-900 border-r border-gray-700 overflow-y-auto">
      {/* Projects */}
      <section className="py-4">
        <h2 className="px-4 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
          Projects
        </h2>
        <ProjectList projects={projects} />
      </section>

      <div className="border-t border-gray-800" />

      {/* Events */}
      <section className="py-4">
        <h2 className="px-4 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
          Upcoming
        </h2>
        <EventList userId={userId} initialEvents={initialEvents} />
      </section>

      <div className="border-t border-gray-800" />

      {/* Reminders */}
      <section className="py-4">
        <h2 className="px-4 mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
          Reminders
        </h2>
        <ReminderList userId={userId} initialReminders={initialReminders} />
      </section>
    </aside>
  );
}
