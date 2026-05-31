"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { User, LogOut, Mail, Loader2 } from "lucide-react";

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
    </svg>
  );
}
import { createClient } from "@/lib/supabase/client";

type GithubStatus = "loading" | "connected" | "disconnected";
type GithubSaveStatus = "idle" | "saving" | "saved" | "error";

export default function ProfilePage() {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [signingOut, setSigningOut] = useState(false);

  const [githubStatus, setGithubStatus] = useState<GithubStatus>("loading");
  const [githubToken, setGithubToken] = useState("");
  const [githubSaveStatus, setGithubSaveStatus] = useState<GithubSaveStatus>("idle");
  const [githubError, setGithubError] = useState<string | null>(null);

  const router = useRouter();

  useEffect(() => {
    async function loadUser() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setEmail(user?.email ?? null);
      setLoading(false);
    }
    loadUser();
  }, []);

  useEffect(() => {
    async function loadGithubStatus() {
      try {
        const res = await fetch("/api/integrations/github");
        if (res.ok) {
          const data = await res.json();
          setGithubStatus(data.connected ? "connected" : "disconnected");
        } else {
          setGithubStatus("disconnected");
        }
      } catch {
        setGithubStatus("disconnected");
      }
    }
    loadGithubStatus();
  }, []);

  async function handleSignOut() {
    setSigningOut(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }

  async function handleSaveGithub() {
    if (githubSaveStatus === "saving") return;
    setGithubSaveStatus("saving");
    setGithubError(null);
    try {
      const res = await fetch("/api/integrations/github", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: githubToken }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setGithubError(data.error ?? "Could not save token.");
        setGithubSaveStatus("error");
        return;
      }
      setGithubSaveStatus("saved");
      setGithubStatus(githubToken.trim() ? "connected" : "disconnected");
    } catch {
      setGithubError("Network error — token not saved.");
      setGithubSaveStatus("error");
    }
  }

  return (
    <main className="flex flex-col h-full bg-bg-root">
      {/* Header */}
      <header className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm">
        <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center shrink-0">
          <User className="h-4 w-4 text-accent" strokeWidth={1.5} />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-sm font-semibold">Profile</h1>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="mx-auto max-w-md p-4 md:p-6">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 text-text-muted animate-spin" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            {/* Avatar */}
            <div className="flex flex-col items-center gap-3 pt-4">
              <div className="w-16 h-16 rounded-full bg-accent/20 flex items-center justify-center border border-border-subtle">
                <span className="text-xl font-semibold text-accent">
                  {email?.charAt(0).toUpperCase() ?? "?"}
                </span>
              </div>
              <p className="text-sm text-text-secondary">{email ?? "—"}</p>
            </div>

            {/* Info card */}
            <div className="bg-bg-surface rounded-xl border border-border-subtle p-4">
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4 text-text-muted shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs text-text-muted">Email</p>
                  <p className="text-sm text-text-primary truncate">{email ?? "—"}</p>
                </div>
              </div>
            </div>

            {/* GitHub integration */}
            <div className="bg-bg-surface rounded-sm border border-border-subtle p-4 space-y-3">
              <div className="flex items-center gap-2">
                <GitHubIcon className="h-4 w-4 text-text-muted shrink-0" />
                <h2 className="text-sm font-medium text-text-primary">GitHub</h2>
                {githubStatus === "connected" && (
                  <span className="text-xs text-accent">Connected</span>
                )}
              </div>
              {githubStatus === "loading" ? (
                <Loader2 className="h-4 w-4 animate-spin text-text-muted" />
              ) : (
                <>
                  <input
                    type="password"
                    value={githubToken}
                    onChange={(e) => {
                      setGithubToken(e.target.value);
                      setGithubSaveStatus("idle");
                    }}
                    placeholder="ghp_…"
                    autoComplete="off"
                    className="w-full rounded-sm border border-border-subtle bg-bg-root px-2.5 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                  {githubSaveStatus === "error" && githubError && (
                    <p className="text-xs text-status-error-fg">{githubError}</p>
                  )}
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleSaveGithub}
                      disabled={githubSaveStatus === "saving"}
                      className="rounded-sm bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {githubSaveStatus === "saving" ? "Saving…" : "Save token"}
                    </button>
                    {githubSaveStatus === "saved" && (
                      <span className="text-xs text-accent">Saved</span>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Sign out */}
            <motion.button
              onClick={handleSignOut}
              disabled={signingOut}
              whileTap={{ scale: 0.98 }}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-status-error-bg border border-status-error-border px-4 py-2.5 text-sm font-medium text-status-error-fg hover:opacity-80 transition-opacity disabled:opacity-50"
            >
              {signingOut ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing out…
                </>
              ) : (
                <>
                  <LogOut className="h-4 w-4" />
                  Sign out
                </>
              )}
            </motion.button>
          </motion.div>
        )}
        </div>
      </div>
    </main>
  );
}
