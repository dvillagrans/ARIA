# ARIA — Personal AI Assistant

Contract-first, provider-agnostic personal assistant. Phase 0 ships the
monorepo skeleton, database schema, FastAPI stub, and Next.js PWA shell.

## Prerequisites

- [Supabase CLI](https://supabase.com/docs/guides/cli) ≥ 1.200
- Docker + Docker Compose v2
- [uv](https://docs.astral.sh/uv/) (Python 3.12)
- [pnpm](https://pnpm.io/) ≥ 9

## Getting Started

Follow these steps **in order** on a clean checkout:

### 1. Copy environment variables

```bash
cp .env.example .env
# Edit .env — fill in the Supabase keys after step 2
```

### 2. Start Supabase (local)

```bash
supabase start
# Copy the anon key and service_role key printed by `supabase status`
# into your .env and frontend/.env.local
```

Magic-link emails in local dev go to Inbucket at http://localhost:54324.
Studio is at http://localhost:54323.

### 3. Apply the database migration

```bash
supabase db reset
# This runs supabase/migrations/0001_init.sql from scratch
```

### 4. Start the FastAPI backend

```bash
docker compose up fastapi --build
# Health check: curl http://localhost:8000/health
```

### 5. Start the Next.js frontend

```bash
cd frontend
pnpm install
pnpm dev
# Open http://localhost:3000
# Unauthenticated visit to /chat redirects to /login
```

## Project structure

```
ARIA/
├── backend/          FastAPI + provider interfaces
├── frontend/         Next.js 16 PWA shell
├── supabase/         Migrations and CLI config
├── docker-compose.yml
├── .env.example
└── README.md
```

## Running backend tests

```bash
cd backend
uv sync
uv run pytest tests/ -v
```

## Environment variables

See `.env.example` for a complete reference with descriptions.
