# ARIA — Personal AI Operating System

**Adaptive Reasoning & Intelligence Assistant**

ARIA is a personal AI operating system built as a Progressive Web App. It captures tasks, notes, events, and reminders in natural language, reasons over all of them to surface what matters most, and connects to external tools via connectors.

Unlike traditional task managers, ARIA doesn't require manual organization. The AI processes every input, decides where it belongs, and presents the right information at the right time.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 + Tailwind CSS (PWA) |
| Backend | FastAPI (async Python) |
| LLM | DeepSeek API — `deepseek-chat` (classifier) + `deepseek-reasoner` (RAG) |
| Embeddings | Qwen3-Embedding-8B via OpenRouter — 4096 dims |
| Database | Supabase (Postgres + pgvector + Realtime + Auth) |
| Connectors | GitHub, Gmail, Google Calendar via HTTP → `/ingest` |
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
                   Connectors (GitHub / Gmail / Calendar)
```

### Provider interfaces

LLM and embedding providers are decoupled behind abstract interfaces. Swapping providers requires only a new implementation — no business logic changes.

```
LLMProvider (abstract)
└── DeepSeekProvider
    ├── classifier → deepseek-chat (fast, low cost)
    └── reasoner  → deepseek-reasoner (full model)

EmbeddingProvider (abstract)
└── QwenEmbeddingProvider
    └── Qwen3-Embedding-8B via OpenRouter · 4096 dims
```

---

## Features

### Phase 0 — Foundation ✅
- Supabase schema with pgvector, FastAPI skeleton, Next.js PWA shell, Auth

### Phase 1 — Core Chat ✅
- Natural language capture (tasks, events, reminders, notes)
- Parallel classify + embed via `asyncio.gather`
- Misclassification correction
- Chat UI + sidebar with Supabase Realtime

### Phase 2 — Memory & RAG ✅
- Semantic search across all records via pgvector
- Context-aware Q&A with `deepseek-reasoner`
- AI-maintained `context_note` per task
- Conversation history

### Phase 3 — Daily Briefing ✅
- Auto-generated briefing on app open
- 3-state cache (fresh / stale / regenerate)
- Deterministic task scoring (deadline + priority + age + energy)
- Briefing invalidation on new captures

### Phase 4 — Connectors ✅
- `POST /ingest` endpoint with API key auth
- GitHub: notification → task/note mapping
- Gmail: heuristic + LLM classification
- Calendar: event sync (next 30 days)
- Deduplication via partial UNIQUE indexes

### Phase 5 — Observability ✅
- 10 Prometheus metrics (chat latency, classification, embedding, RAG, etc.)
- Grafana dashboard (12 panels)
- Alert rules (error rate, latency, service down)
- Extended health endpoint

### Phase 6 — Offline & PWA (planned)
- Service worker + IndexedDB queue
- Sync on reconnect

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
# Edit .env — fill in Supabase keys, DeepSeek API key, DeepInfra API key
```

### 2. Start Supabase

```bash
supabase start
# Copy anon key and service_role key from `supabase status` into .env
```

### 3. Apply migrations

```bash
supabase db reset
```

### 4. Start backend

```bash
docker compose up fastapi --build
# Health check: curl http://localhost:8000/health
```

### 5. Start frontend

```bash
cd frontend
pnpm install
pnpm dev
# Open http://localhost:3000
```

### 6. Start observability (optional)

```bash
docker compose up prometheus grafana -d
# Grafana: http://localhost:3001 (admin/admin)
# Prometheus: http://localhost:9090
```

---

## Project Structure

```
ARIA/
├── backend/
│   ├── app/
│   │   ├── connectors/       GitHub, Gmail, Calendar sync
│   │   ├── core/             Config, deps, metrics registry
│   │   ├── middleware/        Prometheus ASGI middleware
│   │   ├── providers/        LLM + Embedding abstractions
│   │   ├── routes/           FastAPI endpoints (chat, ingest, briefing, health)
│   │   ├── schemas/          Pydantic models (classifier, chat, ingest)
│   │   └── services/         Business logic (classifier, RAG, record_writer)
│   └── tests/                pytest suite (189 tests)
├── frontend/
│   ├── app/                  Next.js app router (chat, login, API routes)
│   ├── components/           Chat UI, Sidebar, MessageList
│   └── lib/                  Supabase client, hooks, offline queue
├── supabase/
│   ├── migrations/           SQL schema + pgvector indexes
│   └── config.toml
├── docker/
│   ├── prometheus/           Scrape config + alert rules
│   └── grafana/              Dashboards + provisioning
├── docker-compose.yml        FastAPI + Prometheus + Grafana
└── scripts/                  OAuth bootstrap utilities
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Classify, embed, and process a user message |
| `POST` | `/ingest` | Ingest external records (API key auth) |
| `GET` | `/briefing` | Get or generate daily briefing |
| `POST` | `/connectors/sync/github` | Sync GitHub notifications |
| `POST` | `/connectors/sync/gmail` | Sync Gmail messages |
| `POST` | `/connectors/sync/calendar` | Sync Google Calendar events |
| `GET` | `/health` | Health check with metrics readiness |
| `GET` | `/metrics` | Prometheus metrics (text format) |

---

## Testing

```bash
# Backend tests
cd backend
uv sync
uv run pytest tests/ -v

# Frontend tests
cd frontend
pnpm test
```

---

## Environment Variables

See `.env.example` for a complete reference.

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `DEEPSEEK_API_KEY` | DeepSeek API key for LLM |
| `DEEPINFRA_API_KEY` | DeepInfra/OpenRouter API key for embeddings |
| `CORS_ORIGINS` | Comma-separated allowed origins (dev) |

---

## License

Private — personal project.
