"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { FolderKanban, Calendar, Bell } from "lucide-react";
import ProjectList, { Project } from "./ProjectList";
import EventList, { CalendarEvent } from "./EventList";
import ReminderList, { Reminder } from "./ReminderList";

interface SidebarProps {
  userId: string;
  projects: Project[];
  initialEvents?: CalendarEvent[];
  initialReminders?: Reminder[];
}

const sectionTitle = "px-4 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-muted";

export default function Sidebar({
  userId,
  projects,
  initialEvents = [],
  initialReminders = [],
}: SidebarProps) {
  return (
    <aside className="flex flex-col w-64 shrink-0 bg-bg-surface border-r border-bg-elevated overflow-y-auto scrollbar-thin h-full">
      {/* Brand header — links to general chat */}
      <Link
        href="/chat"
        className="shrink-0 flex items-center gap-2.5 px-4 py-3 border-b border-bg-elevated hover:bg-bg-elevated/50 transition-colors"
      >
        <img src="/logo.svg" alt="ARIA" className="w-7 h-7 rounded-lg" />
        <span className="text-sm font-semibold">ARIA</span>
      </Link>

      {/* Projects */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.05 }}
        className="py-3"
      >
        <h2 className={sectionTitle}>
          <span className="flex items-center gap-1.5">
            <FolderKanban className="h-3 w-3" />
            Projects
          </span>
        </h2>
        <ProjectList projects={projects} />
      </motion.section>

      <div className="border-t border-bg-elevated mx-3" />

      {/* Events */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="py-3"
      >
        <h2 className={sectionTitle}>
          <span className="flex items-center gap-1.5">
            <Calendar className="h-3 w-3" />
            Upcoming
          </span>
        </h2>
        <EventList userId={userId} initialEvents={initialEvents} />
      </motion.section>

      <div className="border-t border-bg-elevated mx-3" />

      {/* Reminders */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="py-3"
      >
        <h2 className={sectionTitle}>
          <span className="flex items-center gap-1.5">
            <Bell className="h-3 w-3" />
            Reminders
          </span>
        </h2>
        <ReminderList userId={userId} initialReminders={initialReminders} />
      </motion.section>
    </aside>
  );
}
