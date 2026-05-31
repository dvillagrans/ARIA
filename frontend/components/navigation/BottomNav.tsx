"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle, FolderKanban, User } from "lucide-react";

interface Tab {
  id: string;
  label: string;
  href: string;
  icon: typeof MessageCircle;
}

const tabs: Tab[] = [
  { id: "chat", label: "Chat", href: "/chat", icon: MessageCircle },
  { id: "projects", label: "Projects", href: "/projects", icon: FolderKanban },
  { id: "profile", label: "Profile", href: "/profile", icon: User },
];

function isTabActive(pathname: string, href: string): boolean {
  if (href === "/chat") return pathname === "/chat";
  if (href === "/projects") return pathname === "/projects" || pathname.startsWith("/projects/");
  return pathname.startsWith(href);
}

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-bg-surface/95 backdrop-blur-lg border-t border-border-subtle pb-safe">
      <div className="flex h-14 items-center justify-around px-2">
        {tabs.map((tab) => {
          const active = isTabActive(pathname, tab.href);
          const Icon = tab.icon;

          return (
            <Link
              key={tab.id}
              href={tab.href}
              className="relative flex flex-col items-center justify-center min-w-0 flex-1 h-full tap-highlight-transparent select-none"
            >
              <AnimatePresence>
                {active && (
                  <motion.div
                    layoutId="bottom-nav-indicator"
                    className="absolute top-0 h-0.5 w-12 rounded-b-full bg-accent"
                    initial={false}
                    transition={{ type: "spring", stiffness: 500, damping: 35 }}
                  />
                )}
              </AnimatePresence>
              <Icon
                className={`h-5 w-5 transition-colors duration-200 ${
                  active ? "text-accent" : "text-text-muted"
                }`}
                strokeWidth={2}
              />
              <span
                className={`text-xs mt-0.5 font-medium transition-colors duration-200 ${
                  active ? "text-accent" : "text-text-muted"
                }`}
              >
                {tab.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
