"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { motion } from "framer-motion";
import { Sparkles, Loader2 } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError("Invalid email or password.");
    } else {
      router.push("/chat");
    }

    setLoading(false);
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4 bg-gradient-to-b from-bg-root via-bg-root to-bg-surface">
      <div className="w-full max-w-sm animate-fade-in-up">
        <div className="bg-bg-surface/80 backdrop-blur-sm border border-bg-elevated rounded-2xl shadow-md p-6 space-y-6">
          {/* Logo + Title */}
          <div className="space-y-3 text-center">
            <div className="mx-auto w-12 h-12 rounded-xl bg-accent/15 flex items-center justify-center">
              <Sparkles className="h-6 w-6 text-accent" strokeWidth={1.5} />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">ARIA</h1>
              <p className="text-sm text-text-muted mt-1">Sign in to continue</p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-3">
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="w-full rounded-xl bg-bg-elevated border border-bg-hover px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/15 disabled:opacity-50 transition-all"
              />
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                className="w-full rounded-xl bg-bg-elevated border border-bg-hover px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/15 disabled:opacity-50 transition-all"
              />
            </div>

            <motion.button
              type="submit"
              disabled={loading || !email || !password}
              whileTap={{ scale: 0.98 }}
              className="w-full rounded-xl bg-gradient-to-r from-accent to-accent-hover px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-accent/20 transition-shadow hover:shadow-lg hover:shadow-accent/30"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </span>
              ) : (
                "Sign in"
              )}
            </motion.button>
          </form>

          {/* Error */}
          {error && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              role="alert"
              className="text-center text-sm text-red-400"
            >
              {error}
            </motion.p>
          )}
        </div>
      </div>
    </main>
  );
}
