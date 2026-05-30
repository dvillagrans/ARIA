# Next.js
- Use Next.js 16 (not 15.x). Confidence: 0.85
- Configure `turbopack.root` in next.config.mjs to fix lockfile detection warnings. Confidence: 0.75
- Use `proxy.ts` instead of `middleware.ts` (Next.js 16 convention). Confidence: 0.75

# workflow
- "Sigue" means advance/continue to the next SDD phase. Confidence: 0.80

# auth
- Use simple email+password login with Supabase Auth, no registration flow (this is a personal app). Confidence: 0.85

# database
- Use a single unified migration file instead of multiple sequential migrations. Confidence: 0.80

# embedding
- Use OpenRouter (not DeepInfra) for embedding API. Confidence: 0.75
- Use qwen/qwen3-embedding-8b model with 4096 dimensions. Confidence: 0.70
- Disable HNSW indexes when vector dimensions exceed pgvector's 2000-dim HNSW limit. Confidence: 0.60

# frontend
- Wrap `fastapiResponse.json()` in try/catch in Next.js API routes to handle non-JSON error responses gracefully. Confidence: 0.65
