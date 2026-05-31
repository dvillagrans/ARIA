"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ExternalLink } from "lucide-react";

export interface ProjectLink {
  label: string;
  url: string;
}

interface Props {
  projectId: string;
  initialLinks: ProjectLink[];
  initialNotes: string;
  initialGithubRepo: string;
}

type Status = "idle" | "saving" | "saved" | "error";

function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url.trim());
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export default function ProjectInfoEditor({
  projectId,
  initialLinks,
  initialNotes,
  initialGithubRepo,
}: Props) {
  const router = useRouter();
  const [links, setLinks] = useState<ProjectLink[]>(initialLinks);
  const [notes, setNotes] = useState(initialNotes);
  const [githubRepo, setGithubRepo] = useState(initialGithubRepo);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  function addLink() {
    setLinks((prev) => [...prev, { label: "", url: "" }]);
    setStatus("idle");
  }

  function updateLink(index: number, field: keyof ProjectLink, value: string) {
    setLinks((prev) =>
      prev.map((l, i) => (i === index ? { ...l, [field]: value } : l))
    );
    setStatus("idle");
  }

  function removeLink(index: number) {
    setLinks((prev) => prev.filter((_, i) => i !== index));
    setStatus("idle");
  }

  async function handleSave() {
    if (status === "saving") return;

    // Drop empty rows the user never filled in.
    const filled = links.filter((l) => l.label.trim() || l.url.trim());
    const invalid = filled.find((l) => !isValidUrl(l.url));
    if (invalid) {
      setError(`"${invalid.label || invalid.url}" needs a valid http(s) URL.`);
      setStatus("error");
      return;
    }

    const cleaned = filled.map((l) => ({ label: l.label.trim(), url: l.url.trim() }));

    setStatus("saving");
    setError(null);
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ links: cleaned, context: notes, github_repo: githubRepo.trim() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.error ?? "Could not save changes.");
        setStatus("error");
        return;
      }
      setLinks(cleaned);
      setStatus("saved");
      router.refresh();
    } catch {
      setError("Network error — changes not saved.");
      setStatus("error");
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      {status === "error" && error && (
        <div role="alert" className="banner banner-error rounded-sm">
          <span className="flex-1">{error}</span>
        </div>
      )}

      {/* Links */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs uppercase tracking-widest text-text-muted">Links</h2>
          <button
            onClick={addLink}
            className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors focus-ring"
          >
            <Plus className="h-3.5 w-3.5" />
            Add link
          </button>
        </div>

        {links.length === 0 ? (
          <p className="text-xs text-text-muted">
            No links yet. Add a repository, docs, or any URL.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {links.map((link, i) => {
              const valid = isValidUrl(link.url);
              return (
                <div
                  key={i}
                  className="flex flex-col gap-2 border border-border-subtle rounded-sm p-2 sm:flex-row sm:items-center"
                >
                  <input
                    value={link.label}
                    onChange={(e) => updateLink(i, "label", e.target.value)}
                    placeholder="Label (e.g. Repository)"
                    className="w-full sm:w-44 shrink-0 rounded-sm border border-border-subtle bg-bg-root px-2.5 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                  <input
                    value={link.url}
                    onChange={(e) => updateLink(i, "url", e.target.value)}
                    placeholder="https://…"
                    inputMode="url"
                    className="w-full flex-1 min-w-0 rounded-sm border border-border-subtle bg-bg-root px-2.5 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                  <div className="flex items-center gap-1 shrink-0 self-end sm:self-auto">
                    {valid && (
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 rounded-sm text-text-muted hover:text-accent hover:bg-bg-elevated transition-colors focus-ring"
                        aria-label="Open link"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                    <button
                      onClick={() => removeLink(i)}
                      className="p-1.5 rounded-sm text-text-muted hover:text-error hover:bg-status-error-bg transition-colors focus-ring"
                      aria-label="Remove link"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* GitHub repo */}
      <section>
        <h2 className="text-xs uppercase tracking-widest text-text-muted mb-2">GitHub Repo</h2>
        <input
          value={githubRepo}
          onChange={(e) => {
            setGithubRepo(e.target.value);
            setStatus("idle");
          }}
          placeholder="owner/repo or https://github.com/owner/repo"
          className="w-full rounded-sm border border-border-subtle bg-bg-root px-2.5 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition-colors"
        />
        <p className="mt-1 text-xs text-text-muted">Used to sync issues, PRs, and README into context.</p>
      </section>

      {/* Notes */}
      <section>
        <h2 className="text-xs uppercase tracking-widest text-text-muted mb-2">Notes</h2>
        <textarea
          value={notes}
          onChange={(e) => {
            setNotes(e.target.value);
            setStatus("idle");
          }}
          placeholder="Anything worth remembering about this project…"
          rows={5}
          className="w-full rounded-sm border border-border-subtle bg-bg-root px-3 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent transition-colors resize-y"
        />
      </section>

      {/* Save */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={status === "saving"}
          className="rounded-sm bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus-ring"
        >
          {status === "saving" ? "Saving…" : "Save"}
        </button>
        {status === "saved" && (
          <span className="text-xs text-accent">Saved</span>
        )}
      </div>
    </div>
  );
}
