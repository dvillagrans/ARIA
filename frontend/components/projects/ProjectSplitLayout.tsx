"use client";

import { useEffect, useState, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import InfoSidePanel from "./InfoSidePanel";

interface Props {
  children: React.ReactNode;
  projectId: string;
  projectName: string;
  projectColor: string;
  projectContext: string | null;
  projectGithubRepo: string | null;
}

export default function ProjectSplitLayout({
  children,
  projectId,
  projectName,
  projectColor,
  projectContext,
  projectGithubRepo,
}: Props) {
  const storageKey = "aria-panel-" + projectId;

  // Default false to avoid SSR mismatch; read localStorage after mount
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(storageKey);
    if (stored === "true") setCollapsed(true);
    setMounted(true);
  }, [storageKey]);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(storageKey, String(next));
      return next;
    });
  }, [storageKey]);

  // ⌘I / Ctrl+I shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "i") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggle]);

  // Panel width: 0 when collapsed, 40% when open
  const panelWidth = !mounted || collapsed ? 0 : "40%";

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Chat area — takes remaining space */}
      <div className="flex flex-col min-h-0 flex-1" style={{ minWidth: 0 }}>
        {children}
      </div>

      {/* Divider + toggle button — always visible on desktop */}
      <div className="hidden lg:flex items-center relative shrink-0" style={{ width: "1px", backgroundColor: "var(--color-border-subtle)" }}>
        <button
          onClick={toggle}
          title={collapsed ? "Show panel (⌘I)" : "Hide panel (⌘I)"}
          className="absolute top-1/2 -translate-y-1/2 left-1/2 -translate-x-1/2 z-20
                     w-5 h-8 flex items-center justify-center
                     bg-bg-elevated border border-border-subtle rounded-sm
                     text-text-muted hover:text-text-primary transition-colors"
        >
          {collapsed ? (
            <ChevronLeft className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
        </button>
      </div>

      {/* Panel — desktop only, animated width */}
      <div
        className="hidden lg:flex flex-col min-h-0 overflow-hidden shrink-0"
        style={{
          width: panelWidth,
          transition: "width 200ms ease-in-out",
        }}
      >
        {mounted && !collapsed && (
          <InfoSidePanel
            projectId={projectId}
            projectName={projectName}
            projectColor={projectColor}
            projectContext={projectContext}
            projectGithubRepo={projectGithubRepo}
          />
        )}
      </div>
    </div>
  );
}
