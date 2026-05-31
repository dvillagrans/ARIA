"use client";

import { useEffect, useState } from "react";
import { Loader2, Star, GitFork } from "lucide-react";

interface RepoMeta {
  name: string;
  full_name: string;
  description: string | null;
  stars: number;
  forks: number;
  language: string | null;
  default_branch: string;
}

interface Issue {
  number: number;
  title: string;
  labels: string[];
  url: string;
  created_at: string;
}

interface PR {
  number: number;
  title: string;
  head: string;
  base: string;
  url: string;
  created_at: string;
}

interface GitHubData {
  repo: RepoMeta | null;
  issues: Issue[];
  prs: PR[];
  readme: string | null;
}

function normalizeRepo(raw: string): string {
  return raw
    .trim()
    .replace(/^https?:\/\/(www\.)?github\.com\//, "")
    .replace(/^github\.com\//, "")
    .replace(/\/+$/, "");
}

function truncateReadme(text: string, maxLines: number): { text: string; truncated: boolean } {
  const lines = text.split("\n");
  if (lines.length <= maxLines) return { text, truncated: false };
  return { text: lines.slice(0, maxLines).join("\n"), truncated: true };
}

interface GitHubRepoPanelProps {
  repo: string;
  className?: string;
}

export default function GitHubRepoPanel({ repo, className }: GitHubRepoPanelProps) {
  const [data, setData] = useState<GitHubData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const normalized = normalizeRepo(repo);
    if (!normalized) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    fetch(`/api/integrations/github/repo?repo=${encodeURIComponent(normalized)}`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) {
          setError(json.error ?? "Unknown error");
          return;
        }
        setData(json as GitHubData);
      })
      .catch(() => {
        setError("Network error");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [repo]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-xs text-text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading GitHub data…
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-xs text-text-muted py-4">
        {error === "GitHub not connected"
          ? "Connect GitHub from your profile to see repo data."
          : `Could not load GitHub data: ${error}`}
      </p>
    );
  }

  if (!data) return null;

  const { repo: repoMeta, issues, prs, readme } = data;

  const hasNoData = issues.length === 0 && prs.length === 0 && readme === null;

  return (
    <div className={className ?? "flex flex-col gap-4 mt-6 max-w-2xl"}>
      {/* Repo meta bar */}
      {repoMeta && (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3 flex-wrap text-xs text-text-muted">
            <span className="text-text-primary font-medium">{repoMeta.full_name}</span>
            {repoMeta.language && (
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent inline-block" />
                {repoMeta.language}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Star className="h-3 w-3" />
              {repoMeta.stars}
            </span>
            <span className="flex items-center gap-1">
              <GitFork className="h-3 w-3" />
              {repoMeta.forks}
            </span>
          </div>
          {repoMeta.description && (
            <p className="text-xs text-text-secondary">{repoMeta.description}</p>
          )}
        </div>
      )}

      {hasNoData ? (
        <p className="text-xs text-text-muted">No data yet — run a sync from Profile.</p>
      ) : (
        <>
          {/* Issues */}
          <div className="border border-border-subtle rounded-sm overflow-hidden">
            <div className="px-3 py-2 bg-bg-elevated text-xs uppercase tracking-widest text-text-muted flex items-center justify-between">
              <span>Issues</span>
              <span>{issues.length} open</span>
            </div>
            {issues.length === 0 ? (
              <p className="px-3 py-3 text-xs text-text-muted">No open issues.</p>
            ) : (
              issues.map((issue) => (
                <a
                  key={issue.number}
                  href={issue.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-2 border-t border-border-subtle flex items-start gap-2 hover:bg-bg-elevated transition-colors"
                >
                  <span className="text-xs text-text-muted shrink-0">#{issue.number}</span>
                  <span className="text-sm text-text-primary flex-1 min-w-0 truncate">
                    {issue.title}
                  </span>
                  {issue.labels.length > 0 && (
                    <div className="flex items-center gap-1 shrink-0 flex-wrap">
                      {issue.labels.map((label) => (
                        <span
                          key={label}
                          className="rounded-sm px-1.5 py-0.5 text-[10px] bg-bg-elevated text-text-muted"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </a>
              ))
            )}
          </div>

          {/* Pull Requests */}
          <div className="border border-border-subtle rounded-sm overflow-hidden">
            <div className="px-3 py-2 bg-bg-elevated text-xs uppercase tracking-widest text-text-muted flex items-center justify-between">
              <span>Pull Requests</span>
              <span>{prs.length} open</span>
            </div>
            {prs.length === 0 ? (
              <p className="px-3 py-3 text-xs text-text-muted">No open pull requests.</p>
            ) : (
              prs.map((pr) => (
                <a
                  key={pr.number}
                  href={pr.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-2 border-t border-border-subtle flex items-start gap-2 hover:bg-bg-elevated transition-colors"
                >
                  <span className="text-xs text-text-muted shrink-0">#{pr.number}</span>
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-sm text-text-primary truncate">{pr.title}</span>
                    <span className="text-[10px] text-text-muted mt-0.5">
                      {pr.base} ← {pr.head}
                    </span>
                  </div>
                </a>
              ))
            )}
          </div>

          {/* README */}
          <div className="border border-border-subtle rounded-sm overflow-hidden">
            <div className="px-3 py-2 bg-bg-elevated text-xs uppercase tracking-widest text-text-muted">
              README
            </div>
            {readme === null ? (
              <p className="px-3 py-3 text-xs text-text-muted">No README found.</p>
            ) : (
              <div className="px-3 py-2 border-t border-border-subtle">
                {(() => {
                  const { text, truncated } = truncateReadme(readme, 40);
                  return (
                    <pre className="font-mono text-xs text-text-secondary whitespace-pre-wrap break-words leading-relaxed max-h-64 overflow-y-auto scrollbar-thin">
                      {text}
                      {truncated && "…"}
                    </pre>
                  );
                })()}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
