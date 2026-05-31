"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

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
    <main className="flex min-h-dvh flex-col bg-bg-root">
      {/* Top strip */}
      <div className="flex items-center gap-2.5 px-6 pt-8">
        <img src="/logo.svg" alt="ARIA" className="w-8 h-8 rounded-xl" />
        <span className="text-sm font-semibold tracking-tight">ARIA</span>
      </div>

      {/* Centered form */}
      <div className="flex flex-1 items-center justify-center px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="w-full max-w-sm"
        >
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
            <p className="text-sm text-text-muted mt-1">Sign in to your account to continue.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="block text-xs font-medium text-text-secondary">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="w-full h-11 rounded-xl bg-bg-elevated border border-border-subtle px-4 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent disabled:opacity-50 transition-colors"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="block text-xs font-medium text-text-secondary">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                className="w-full h-11 rounded-xl bg-bg-elevated border border-border-subtle px-4 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent disabled:opacity-50 transition-colors"
              />
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                role="alert"
                className="banner banner-error rounded-xl"
              >
                {error}
              </motion.div>
            )}

            <motion.button
              type="submit"
              disabled={loading || !email || !password}
              whileTap={{ scale: 0.98 }}
              className="w-full h-11 rounded-xl bg-accent px-4 text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent-hover transition-colors"
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
        </motion.div>
      </div>
    </main>
  );
}
