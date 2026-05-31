import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

function normalizeRepo(raw: string): string {
  return raw
    .trim()
    .replace(/^https?:\/\/(www\.)?github\.com\//, "")
    .replace(/^github\.com\//, "")
    .replace(/\/+$/, "");
}

interface GitHubIssueRaw {
  number: number;
  title: string;
  html_url: string;
  created_at: string;
  pull_request?: unknown;
  labels: Array<{ name: string }>;
}

interface GitHubPRRaw {
  number: number;
  title: string;
  html_url: string;
  created_at: string;
  head: { ref: string };
  base: { ref: string };
}

interface GitHubRepoRaw {
  name: string;
  full_name: string;
  description: string | null;
  stargazers_count: number;
  forks_count: number;
  language: string | null;
  default_branch: string;
}

interface GitHubReadmeRaw {
  content: string;
  encoding: string;
}

async function safeFetch<T>(url: string, headers: HeadersInit): Promise<T | null> {
  try {
    const res = await fetch(url, {
      headers,
      next: { revalidate: 300 }, // cache 5 min server-side
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function GET(req: Request): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const rawRepo = searchParams.get("repo");

  if (!rawRepo) {
    return NextResponse.json({ error: "repo param is required" }, { status: 400 });
  }

  const repo = normalizeRepo(rawRepo);

  const { data } = await supabase
    .from("connector_state")
    .select("state_json")
    .eq("user_id", user.id)
    .eq("provider", "github")
    .maybeSingle();

  const token = (data?.state_json as Record<string, unknown>)?.token as string ?? "";

  if (!token) {
    return NextResponse.json({ error: "GitHub not connected" }, { status: 403 });
  }

  const githubHeaders = {
    Authorization: `token ${token}`,
    Accept: "application/vnd.github+json",
  };

  const base = `https://api.github.com/repos/${repo}`;

  const [repoRaw, issuesRaw, prsRaw, readmeRaw] = await Promise.all([
    safeFetch<GitHubRepoRaw>(base, githubHeaders),
    safeFetch<GitHubIssueRaw[]>(`${base}/issues?state=open&per_page=20&sort=updated`, githubHeaders),
    safeFetch<GitHubPRRaw[]>(`${base}/pulls?state=open&per_page=20&sort=updated`, githubHeaders),
    safeFetch<GitHubReadmeRaw>(`${base}/readme`, githubHeaders),
  ]);

  const repoData = repoRaw
    ? {
        name: repoRaw.name,
        full_name: repoRaw.full_name,
        description: repoRaw.description ?? null,
        stars: repoRaw.stargazers_count,
        forks: repoRaw.forks_count,
        language: repoRaw.language ?? null,
        default_branch: repoRaw.default_branch,
      }
    : null;

  const issues = Array.isArray(issuesRaw)
    ? issuesRaw
        .filter((item) => !("pull_request" in item))
        .map((item) => ({
          number: item.number,
          title: item.title,
          labels: item.labels.map((l) => l.name),
          url: item.html_url,
          created_at: item.created_at,
        }))
    : [];

  const prs = Array.isArray(prsRaw)
    ? prsRaw.map((item) => ({
        number: item.number,
        title: item.title,
        head: item.head.ref,
        base: item.base.ref,
        url: item.html_url,
        created_at: item.created_at,
      }))
    : [];

  let readme: string | null = null;
  if (readmeRaw?.content && readmeRaw.encoding === "base64") {
    const decoded = Buffer.from(readmeRaw.content, "base64").toString("utf-8");
    readme = decoded.slice(0, 3000).trim();
  }

  return NextResponse.json({ repo: repoData, issues, prs, readme });
}
