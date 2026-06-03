# ARIA — Personal AI Operating System

**Adaptive Reasoning & Intelligence Assistant**

ARIA is a personal AI operating system built as a Progressive Web App. It captures tasks, notes, events, and reminders in natural language, reasons over your data with RAG, helps you study structured material, and connects to external tools via connectors.

Unlike traditional task managers, ARIA does not require manual organization. The AI classifies every input, decides where it belongs, and surfaces what matters — including daily briefings and study guides when you need them.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 + Tailwind CSS 4 + PWA (`@ducanh2912/next-pwa`) |
| Backend | FastAPI (async Python) |
| LLM | DeepSeek — `deepseek-chat` (classifier) + `deepseek-reasoner` (reasoning) |
| Embeddings | Qwen3-Embedding-8B via OpenRouter — **4096 dims** |
| Database | Supabase (Postgres + pgvector + Realtime + Auth + Storage) |
| Web search | Tavily API (optional) + DuckDuckGo fallback |
| Connectors | GitHub, Gmail, Google Calendar → `POST /ingest` |
| Observability | Prometheus + Grafana |

---

## Architecture

```
User → Next.js (PWA) → FastAPI → Supabase
                        ↓
                   DeepSeek (classify + reason)
                   Qwen3 (embed)
                        ↓
                   pgvector (semantic search)
                        ↓
        Study tools · Web search · Connectors · Documents
```

### Chat intent routing

Every message is classified into one intent. The backend routes to the right service:

| Intent | Example | Handler |
|---|---|---|
| `capture` | "recordar pagar colegiatura el viernes" | Classify → embed → write record |
| `correction` | "eso era un evento, no una tarea" | Fix previous classification |
| `context_note_update` | "bloqueado esperando respuesta de Alex" | Update task `context_note` |
| `query` | "¿qué tareas vencen esta semana?" | RAG over pgvector |
| `study` | "ayúdame a estudiar esto" + URLs | Study service (plan, quiz, …) |
| `web_search` | "busca lo último sobre RAG agents" | Tavily / DuckDuckGo |
| `conversation` | "gracias", "hola" | Short natural reply |

### Provider interfaces

LLM and embedding providers are decoupled behind abstract interfaces. Swapping providers requires only a new implementation.

```
LLMProvider (abstract)
└── DeepSeekProvider
    ├── classify → deepseek-chat
    └── reason   → deepseek-reasoner

EmbeddingProvider (abstract)
└── QwenEmbeddingProvider
    └── Qwen3-Embedding-8B · 4096 dims
```

---

## Features

### Phase 0 — Foundation ✅
- Supabase schema with pgvector (`vector(4096)`), FastAPI skeleton, Next.js PWA shell, Auth

### Phase 1 — Core Chat ✅
- Natural language capture (tasks, events, reminders, notes)
- Parallel classify + embed via `asyncio.gather`
- Misclassification correction
- Chat UI + sidebar / bottom nav with Supabase Realtime

### Phase 2 — Memory & RAG ✅
- Semantic search across records via pgvector
- Context-aware Q&A with `deepseek-reasoner`
- AI-maintained `context_note` per task
- Conversation history (with metadata for follow-ups)

### Phase 3 — Daily Briefing ✅
- Auto-generated briefing on app open
- 3-state cache (fresh / stale / regenerate)
- Deterministic task scoring
- Briefing invalidation on new captures

### Phase 4 — Connectors ✅
- `POST /ingest` with API key auth
- GitHub, Gmail, Google Calendar sync
- Deduplication via partial UNIQUE indexes

### Phase 5 — Observability ✅
- Prometheus metrics + Grafana dashboards + alert rules

### Phase 6 — Offline & PWA 🟡
- Service worker via `@ducanh2912/next-pwa` (production builds)
- IndexedDB offline message queue + drain on reconnect
- Dev stub for `/sw.js`

### Phase 7 — Study Tools ✅
- **Study intent** with modes: `study_plan`, `quiz`, `explain`, `flashcards`, `summarize`
- URL extraction from PDFs, arXiv, HTML articles (YouTube/Drive: metadata only)
- **Follow-up context** — quiz and plan regeneration without re-pasting links
- Markdown-rendered assistant responses in chat (`react-markdown` + GFM tables)
- Optional web search for external/current information

### Projects & Documents ✅
- Per-project chat scoped to a project
- Document upload (PDF, TXT, MD) to Supabase Storage

---

## Study assistant (quick guide)

Paste material or links once, then continue in the same thread:

```
Ayúdame a estudiar esto
[lista de temas + URLs]

→ Plan de estudio completo (markdown)

creo que NLP lo domino, hazme un par de preguntas
→ Quiz enfocado en NLP (usa historial, no pide links de nuevo)

vuelve a darme el plan completo
→ Regenera el plan desde contexto previo
```

Follow-up messages recover URLs and conversation context from prior turns automatically.

---

## Getting Started

### Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli) ≥ 1.200
- Docker + Docker Compose v2
- [uv](https://docs.astral.sh/uv/) (Python 3.12)
- [pnpm](https://pnpm.io/) ≥ 9

### 1. Clone and configure

```bash
git clone https://github.com/<user>/ARIA.git
cd ARIA
cp .env.example .env
# Fill Supabase keys, DEEPSEEK_API_KEY, DEEPINFRA_API_KEY
# Optional: TAVILY_API_KEY for web search
```

### 2. Start Supabase

```bash
supabase start
# Copy anon + service_role keys from `supabase status` into .env and frontend/.env.local
```

### 3. Apply migrations

```bash
supabase db reset
```

### 4. Start backend

```bash
docker compose up fastapi --build
# curl http://localhost:8000/health
```

### 5. Start frontend

```bash
cd frontend
pnpm install
pnpm dev
# http://localhost:3000
```

### 6. Observability (optional)

```bash
docker compose up prometheus grafana -d
# Grafana: http://localhost:3001 · Prometheus: http://localhost:9090
```

---

## Project Structure

```
ARIA/
├── backend/
│   ├── app/
│   │   ├── connectors/       GitHub, Gmail, Calendar
│   │   ├── core/             Config, deps, metrics
│   │   ├── providers/        LLM + Embedding abstractions
│   │   ├── routes/           chat, briefing, ingest, documents, …
│   │   ├── schemas/          Classifier, chat, ingest models
│   │   └── services/         classifier, RAG, study, pdf, web_search, …
│   └── tests/                pytest (229 tests)
├── frontend/
│   ├── app/                  App router (chat, projects, login, API routes)
│   ├── components/chat/      ChatView, MessageList, MarkdownMessage
│   └── lib/hooks/            offline queue, reminder poll
├── supabase/migrations/      Schema, pgvector, documents, RLS
├── docker/                   Prometheus + Grafana
└── ARIA_PRD_v1.md            Product requirements
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Classify, route, and respond to a user message |
| `POST` | `/ingest` | Ingest external records (API key auth) |
| `GET` | `/briefing` | Daily briefing (cached) |
| `POST` | `/connectors/sync/*` | GitHub, Gmail, Calendar sync |
| `GET` | `/health` | Health + metrics readiness |
| `GET` | `/metrics` | Prometheus scrape target |

Frontend proxies auth-sensitive routes through Next.js API routes (`/api/chat`, `/api/briefing`, …).

---

## Testing

```bash
# Backend
cd backend && uv sync && uv run pytest tests/ -v

# Frontend
cd frontend && pnpm test
```

---

## Environment Variables

See `.env.example`. Key variables:

| Variable | Description |
|---|---|
| `SUPABASE_URL` / keys | Supabase project |
| `DEEPSEEK_API_KEY` | LLM classifier + reasoner |
| `DEEPINFRA_API_KEY` | Qwen3 embeddings (OpenRouter) |
| `TAVILY_API_KEY` | Optional — web search primary provider |
| `NEXT_PUBLIC_API_URL` | Frontend → FastAPI base URL |

---

## License

Private — personal project.
