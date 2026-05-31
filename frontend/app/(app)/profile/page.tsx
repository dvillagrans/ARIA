"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { User, LogOut, Mail, Loader2 } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export default function ProfilePage() {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [signingOut, setSigningOut] = useState(false);
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

  async function handleSignOut() {
    setSigningOut(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
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
