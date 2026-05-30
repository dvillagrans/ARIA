# Skill Registry — ARIA

<!-- Updated by sdd-init on 2026-05-29. Active agent: Claude Code. -->

Last updated: 2026-05-29

## Sources scanned

### User-level (Claude Code)
- `/home/dvillagran/.claude/skills/` — authoritative for Claude Code sessions

### User-level (other agents, kept for cross-agent compatibility)
- `/home/dvillagran/.config/agents/skills/`
- `/home/dvillagran/.config/opencode/skills/`
- `/home/dvillagran/.agents/skills/`

### Project-level
- `/home/dvillagran/Documentos/personal/ARIA/skills/` — not found
- `/home/dvillagran/Documentos/personal/ARIA/.atl/skills/` — not found
- `/home/dvillagran/Documentos/personal/ARIA/.claude/skills/` — not found

## Contract

**Delegator use only.** This registry is an index, not a summary. Any agent that launches subagents reads it to select relevant skills, then passes exact `SKILL.md` paths for the subagent to read before work.

`SKILL.md` remains the source of truth. Do not inject generated summaries or compact rules by default; pass paths so subagents load the full runtime contract and preserve author intent.

**Path authority for Claude Code**: use paths under `/home/dvillagran/.claude/skills/` for all Claude Code sub-agent launches. The `.config/agents/` paths are equivalent but may not be symlinked — prefer `.claude/skills/`.

## Skills

| Skill | Trigger / description | Scope | Path (Claude Code) |
| --- | --- | --- | --- |
| `branch-pr` | Create Gentle AI pull requests with issue-first checks. Trigger: creating, opening, or preparing PRs for review. | user | `/home/dvillagran/.claude/skills/branch-pr/SKILL.md` |
| `chained-pr` | Trigger: PRs over 400 lines, stacked PRs, review slices. Split oversized changes into chained PRs that protect review focus. | user | `/home/dvillagran/.claude/skills/chained-pr/SKILL.md` |
| `cognitive-doc-design` | Design docs that reduce cognitive load. Trigger: writing guides, READMEs, RFCs, onboarding, architecture, or review-facing docs. | user | `/home/dvillagran/.claude/skills/cognitive-doc-design/SKILL.md` |
| `comment-writer` | Write warm, direct collaboration comments. Trigger: PR feedback, issue replies, reviews, Slack messages, or GitHub comments. | user | `/home/dvillagran/.claude/skills/comment-writer/SKILL.md` |
| `find-skills` | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. | user | `/home/dvillagran/.agents/skills/find-skills/SKILL.md` |
| `go-testing` | Trigger: Go tests, go test coverage, Bubbletea teatest, golden files. Apply focused Go testing patterns. | user | `/home/dvillagran/.claude/skills/go-testing/SKILL.md` |
| `issue-creation` | Create Gentle AI issues with issue-first checks. Trigger: creating GitHub issues, bug reports, or feature requests. | user | `/home/dvillagran/.claude/skills/issue-creation/SKILL.md` |
| `judgment-day` | Trigger: judgment day, dual review, adversarial review, juzgar. Run blind dual review, fix confirmed issues, then re-judge. | user | `/home/dvillagran/.claude/skills/judgment-day/SKILL.md` |
| `skill-creator` | Trigger: new skills, agent instructions, documenting AI usage patterns. Create LLM-first skills with valid frontmatter. | user | `/home/dvillagran/.claude/skills/skill-creator/SKILL.md` |
| `skill-improver` | Trigger: improve skills, audit skills, refactor skills, skill quality. Audit and upgrade existing LLM-first skills. | user | `/home/dvillagran/.claude/skills/skill-improver/SKILL.md` |
| `supabase` | Use when doing ANY task involving Supabase. Triggers: Supabase products (Database, Auth, Edge Functions, Realtime, Storage, Vectors, Cron, Queues); supabase-js, @supabase/ssr in Next.js; auth, RLS, pgvector, migrations, schema changes. | user | `/home/dvillagran/.agents/skills/supabase/SKILL.md` |
| `supabase-postgres-best-practices` | Postgres performance optimization and best practices from Supabase. Use when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations. | user | `/home/dvillagran/.agents/skills/supabase-postgres-best-practices/SKILL.md` |
| `work-unit-commits` | Plan commits as reviewable work units. Trigger: implementation, commit splitting, chained PRs, or keeping tests and docs with code. | user | `/home/dvillagran/.claude/skills/work-unit-commits/SKILL.md` |

## Loading protocol

1. Match task context and target files against the `Trigger / description` column.
2. Pass only the matching `Path` values to the subagent under `## Skills to load before work`.
3. Instruct the subagent to read those exact `SKILL.md` files before reading, writing, reviewing, testing, or creating artifacts.
4. If no matching skill exists, proceed without project skill injection and report `skill_resolution: none`.

## ARIA-specific skill matching guide

| Work context | Relevant skills |
| --- | --- |
| Supabase schema, pgvector, RLS, Auth, Realtime | `supabase`, `supabase-postgres-best-practices` |
| PR creation or review | `branch-pr`, `chained-pr`, `cognitive-doc-design` |
| Large change / >400 lines | `chained-pr`, `work-unit-commits` |
| Implementation (sdd-apply) | `work-unit-commits`, `chained-pr` |
| GitHub issues | `issue-creation` |
| PR/issue comments | `comment-writer` |
| Adversarial review | `judgment-day` |
| Architecture/README docs | `cognitive-doc-design` |
