# ARIA — Personal AI Operating System
### Product Requirements Document

| | |
|---|---|
| **Version** | 1.3.0 |
| **Status** | En desarrollo activo |
| **Author** | Diego |
| **Stack** | Next.js · FastAPI · Supabase · DeepSeek · Qwen3-Embedding · Prometheus |

---

## 1. Overview

ARIA (Adaptive Reasoning & Intelligence Assistant) is a personal AI operating system built as a Progressive Web App. It serves as a unified second brain and productivity assistant — capturing tasks, notes, events, and reminders in natural language, reasoning over all of them to surface what matters most, **helping the user study structured material**, and connecting to external tools via a plug-and-play microservices layer.

Unlike traditional task managers or note-taking tools, ARIA does not require the user to organize, tag, or maintain anything manually. The AI processes every input, decides where it belongs, and presents the right information at the right time without being asked.

---

## 2. Problem statement

The target user manages multiple simultaneous projects across work, school, and personal life. The core pain points are:

- Too many contexts to track — professional projects, academic deliverables, personal commitments
- No single place where all information lives together
- Existing tools require constant manual maintenance to stay useful
- Decision paralysis when sitting down to work — unclear what to do right now
- Knowledge gets lost between sessions — context about decisions, blockers, and progress is forgotten
- **Study prep is fragmented** — links, papers, and videos scattered; hard to turn them into a actionable plan or self-test

The result is cognitive overload: everything feels urgent, nothing gets finished, and the overhead of maintaining productivity tools becomes another task in itself.

---

## 3. Goals & non-goals

### 3.1 Goals

- Provide a single interface for capturing any type of information in natural language
- Automatically classify, organize, and link captured information to the correct project
- Surface a daily briefing and a single recommended action without asking the user anything
- Answer questions about the user's own data using RAG over their full knowledge base
- **Act as a study tutor** — plans, quizzes, explanations, and flashcards from pasted text or URLs
- **Maintain study session context** — follow-up messages ("hazme preguntas de NLP") work without re-pasting material
- Support reminders, events, and payments alongside tasks and notes
- Enable external integrations (GitHub, Gmail, Google Calendar) via isolated microservices
- Be fully observable via Prometheus metrics on every service
- Work offline for capture; sync when connection is restored

### 3.2 Non-goals

- Team collaboration — single-user system
- Built-in calendar UI — events are stored and surfaced, not visually scheduled
- Real-time push notifications in v1 — reminders surface in briefing and poll UI
- Mobile-native app — PWA covers mobile and desktop
- **Full video transcription** — YouTube/Drive links are referenced; content extraction is best-effort for PDF/HTML

---

## 4. Target user

A developer-student hybrid who simultaneously manages professional projects, academic deliverables, and personal commitments. Comfortable with technical tools but frustrated by the overhead of keeping them organized. Prefers to be told what to do next rather than asked questions. Values speed of capture and quality of reasoning over visual polish. **Needs to prep for courses and projects** (e.g. servicio social, AI/NLP curricula) without switching to a separate study app.

---

## 5. System architecture

### 5.1 Layers

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js 16 + Tailwind CSS 4 (PWA) | Chat UI, sidebar/bottom nav, markdown rendering, offline queue |
| Backend core | FastAPI (async) | AI orchestration, RAG, study tools, ingestion. `asyncio.gather` for I/O-bound work |
| LLM provider | DeepSeek via `LLMProvider` | Classification (`deepseek-chat`) + reasoning (`deepseek-reasoner`) |
| Embedding provider | Qwen3-Embedding-8B via OpenRouter | Embeddings de **4096 dims** |
| Database | Supabase | Postgres + pgvector + Realtime + Auth + Storage (documents) |
| Web search | Tavily (optional) + DuckDuckGo fallback | External/current information |
| Integrations | Connectors → `POST /ingest` | GitHub, Gmail, Calendar |
| Observability | Prometheus + Grafana | Latency, errors, AI timings |

### 5.2 Provider interfaces

```
LLMProvider (abstract)
└── DeepSeekProvider
    ├── classifier → deepseek-chat
    └── reasoner  → deepseek-reasoner

EmbeddingProvider (abstract)
└── QwenEmbeddingProvider
    └── Qwen3-Embedding-8B · 4096 dims
```

`EMBEDDING_DIM = 4096` is the source of truth for pgvector indexes and search RPCs.

### 5.3 Data flow — capture

1. User types in chat → `POST /chat`
2. Parallel `classify()` + `embed()` via `asyncio.gather`
3. Record written to Supabase with embedding
4. Confirmation returned; Realtime updates sidebar

### 5.4 Data flow — query (RAG)

1. Classifier returns `query` intent
2. Question embedded → pgvector retrieval across user records
3. Context + question → reasoner → grounded answer

### 5.5 Data flow — study

1. User sends study material (text and/or URLs) — e.g. curriculum with arXiv, YouTube, PDF links
2. Classifier returns `study` intent with `mode` (`study_plan`, `quiz`, `explain`, `flashcards`, `summarize`)
3. **Source resolution:**
   - URLs in current message → download + extract (PDF/HTML via `pdf_service`)
   - No URLs in follow-up → recover from conversation metadata or prior user messages
   - Still empty → use recent conversation transcript as context
4. Content truncated with **equal budget per source** (all topics represented)
5. `study_service.generate()` → reasoner → markdown study output
6. Frontend renders markdown (headings, lists, tables)

**Follow-up examples (same thread, no re-paste):**

| User message | Expected mode | Behavior |
|---|---|---|
| "ayúdame a estudiar esto" + links | `study_plan` | Full structured plan in Spanish |
| "hazme un par de preguntas de NLP" | `quiz` | 2–3 NLP questions from history |
| "vuelve a darme el plan completo" | `study_plan` | Regenerate full plan, not brief summary |
| "explícame RAG más simple" | `explain` | ELI5 on RAG using prior context |

### 5.6 Data flow — web search

1. Classifier returns `web_search` intent
2. Tavily if `TAVILY_API_KEY` set; else DuckDuckGo
3. Snippets passed to reasoner for synthesized answer

### 5.7 Data flow — offline capture

1. Service worker + IndexedDB queue stores raw messages offline
2. On reconnect, queue drains through normal `POST /chat` pipeline
3. Sidebar shows pending count

### 5.8 Data flow — integration connector

Connector → normalize → `POST /ingest` → classify + embed + persist (same as manual capture)

---

## 6. Data model

*(Core tables unchanged from v1.2 — key updates below.)*

### Embeddings

All semantic tables use `vector(4096)` — tasks, events, reminders, notes, conversations.

### `conversations`

| Field | Type | Notes |
|---|---|---|
| metadata | jsonb | Intent, study `mode`, `source_urls` — **enables study follow-ups without re-pasting links** |
| project_id | uuid | Nullable — scopes chat to a project |

### `documents` (Storage + metadata)

Project-scoped file uploads: PDF, TXT, MD. Used for project knowledge; study flow can also ingest public URLs on demand.

---

## 7. Features — scope

### 7.1 Natural language capture ✅

Single chat input. AI determines record type. Target: confirmation in < 2s under normal conditions.

### 7.2 Misclassification correction ✅

Natural language correction using prior turn metadata.

### 7.3 Daily briefing ✅

Cached per calendar day; invalidated on new captures. One recommended task + events + reminders + project summaries.

### 7.4 Contextual question answering ✅

RAG over user data via `query` intent.

### 7.5 Navigation shell ✅

- **Desktop:** fixed sidebar (projects, events, reminders)
- **Mobile:** bottom navigation + full-width chat
- Realtime updates via Supabase

### 7.6 Offline capture 🟡

IndexedDB queue + drain implemented; PWA service worker active in production builds.

### 7.7 Study assistant ✅ *(new in v1.3)*

**Problem:** User receives a reading list (URLs, papers, videos) and needs a tutor — not a dry English summary.

**Solution:** Dedicated `study` intent with modes:

| Mode | Purpose |
|---|---|
| `study_plan` | Structured plan per topic: concepts, what to review, self-check questions, next steps |
| `quiz` | Questions + answers; respects "un par de preguntas" and topic focus |
| `explain` | ELI5 / beginner-friendly explanation |
| `flashcards` | JSON front/back pairs |
| `summarize` | Concise summary (only when explicitly requested) |

**Requirements:**

- Respond in the **same language as the user** (Spanish by default for this user)
- Render assistant output as **markdown** in the UI (headings, bold, tables, links)
- **Session continuity:** follow-ups must not require "Necesito contenido para estudiar" if the thread already contains material
- Truncation must include **all sources** (equal char budget), not drop later URLs
- YouTube/Google Drive: instruct user what to look for in the resource when extraction is minimal

**Non-requirements (v1.3):** automatic video transcription; spaced-repetition scheduling.

### 7.8 Web search ✅ *(new in v1.3)*

`web_search` intent for current/external facts. Tavily primary; DuckDuckGo fallback.

### 7.9 Project-scoped chat & documents ✅

Chat and uploads scoped per project. General chat uses `project_id IS NULL`.

---

## 8. Integration layer — connectors

Unchanged from v1.2: GitHub, Gmail, Calendar → `POST /ingest`.

---

## 9. AI design

### 9.1 Classifier intents

| Intent | When |
|---|---|
| `capture` | New task, event, reminder, note |
| `correction` | Fix previous classification |
| `context_note_update` | Update task context |
| `query` | Question answerable from user data (RAG) |
| `study` | Learn, study, quiz, explain material |
| `web_search` | Explicit external/current info search |
| `conversation` | Greetings, thanks, small talk |

When in doubt between `query` and `study` with URLs or curriculum → **study**.

### 9.2 Two-model strategy

| Role | Model | Used for |
|---|---|---|
| Classifier | `deepseek-chat` | Intent + field extraction |
| Reasoner | `deepseek-reasoner` | RAG, briefing, study output, context_note |

### 9.3 Parallelism

`asyncio.gather(classify, embed)` on every chat message. Briefing queries run in parallel before reasoner call.

### 9.4 Study prompt design

- `study_plan`: mandatory sections (Plan → Por cada tema → Próximos pasos)
- Regenerate full plan when user says message was cut off
- Quiz: variable count; topic-scoped when user names a subject

---

## 10. Observability

Metrics unchanged from v1.2. Recommended additions for study:

| Metric | Description |
|---|---|
| `aria_study_requests_total` | Study intents by mode *(future)* |
| `aria_study_source_recovery_total` | Follow-ups using history vs fresh URLs *(future)* |

---

## 11. Build plan

| Phase | Name | Status | Deliverables |
|---|---|---|---|
| 0 | Foundations | ✅ | Schema, pgvector 4096, FastAPI, Next.js PWA, Auth |
| 1 | Core loop | ✅ | Capture, classify+embed, correction, chat UI |
| 2 | Memory & RAG | ✅ | pgvector search, Q&A, context_note, history |
| 3 | Daily briefing | ✅ | Cache, scoring, invalidation |
| 4 | Connectors | ✅ | `/ingest`, GitHub, Gmail, Calendar |
| 5 | Observability | ✅ | Prometheus, Grafana, alerts |
| 6 | Offline & PWA | 🟡 | SW, IndexedDB queue, sync on reconnect |
| 7 | Study tools | ✅ | Study intent, pdf extraction, follow-up context, markdown UI |
| 8 | Study polish | 📋 | Video metadata enrichment, study metrics, spaced repetition *(optional)* |

---

## 12. Cost estimate

Unchanged — personal use **< $1 USD/mes** (embeddings negligible; reasoner dominates).

---

## 13. Future upgrades

- **Redis message queue** — when connector volume requires decoupling
- **Push notifications** — reminder delivery outside briefing
- **Rich media study** — YouTube transcript API, Google Drive export
- **Spaced repetition** — schedule flashcard reviews
- **Agent mode** — proactive task creation from patterns
- **Embedding dim tuning** — MRL truncation experiments if document length grows

---

*ARIA — Personal AI Operating System · PRD v1.3.0*
