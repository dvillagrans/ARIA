"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";

interface ProjectTabsProps {
  projectId: string;
}

export default function ProjectTabs({ projectId }: ProjectTabsProps) {
  const pathname = usePathname();
  const onInfo = pathname.endsWith("/info");

  const tabs = [
    { id: "chat", label: "Chat", href: `/projects/${projectId}/chat`, active: !onInfo },
    { id: "info", label: "Info", href: `/projects/${projectId}/info`, active: onInfo },
  ];

  return (
    <nav className="flex items-center gap-1">
      {tabs.map((tab) => (
        <Link
          key={tab.id}
          href={tab.href}
          className={`relative px-3 py-1.5 text-xs font-medium transition-colors focus-ring ${
            tab.active ? "text-accent" : "text-text-muted hover:text-text-secondary"
          }`}
        >
          {tab.label}
          {tab.active && (
            <motion.div
              layoutId="project-tab-indicator"
              className="absolute bottom-0 left-2 right-2 h-0.5 bg-accent"
              initial={false}
              transition={{ type: "spring", stiffness: 500, damping: 35 }}
            />
          )}
        </Link>
      ))}
    </nav>
  );
}
