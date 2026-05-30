# ARIA — Personal AI Operating System
### Product Requirements Document

| | |
|---|---|
| **Version** | 1.2.0 |
| **Status** | Ready for development |
| **Author** | Diego |
| **Stack** | Next.js · FastAPI · Supabase · DeepSeek · Qwen3-Embedding · Prometheus |

---

## 1. Overview

ARIA (Adaptive Reasoning & Intelligence Assistant) is a personal AI operating system built as a Progressive Web App. It serves as a unified second brain and productivity assistant — capturing tasks, notes, events, and reminders in natural language, reasoning over all of them to surface what matters most, and connecting to external tools via a plug-and-play microservices layer.

Unlike traditional task managers or note-taking tools, ARIA does not require the user to organize, tag, or maintain anything manually. The AI processes every input, decides where it belongs, and presents the right information at the right time without being asked.

---

## 2. Problem statement

The target user manages multiple simultaneous projects across work, school, and personal life. The core pain points are:

- Too many contexts to track — professional projects, academic deliverables, personal commitments
- No single place where all information lives together
- Existing tools (task managers, calendars, note apps) require constant manual maintenance to stay useful
- Decision paralysis when sitting down to work — unclear what to do right now
- Knowledge gets lost between sessions — context about decisions, blockers, and progress is forgotten

The result is cognitive overload: everything feels urgent, nothing gets finished, and the overhead of maintaining productivity tools becomes another task in itself.

---

## 3. Goals & non-goals

### 3.1 Goals

- Provide a single interface for capturing any type of information in natural language
- Automatically classify, organize, and link captured information to the correct project
- Surface a daily briefing and a single recommended action without asking the user anything
- Answer questions about the user's own data using RAG over their full knowledge base
- Support reminders, events, and payments alongside tasks and notes
- Enable external integrations (GitHub, Gmail, Google Calendar) via isolated microservices
- Be fully observable via Prometheus metrics on every service
- Work offline for capture; sync when connection is restored

### 3.2 Non-goals

- Team collaboration features — this is a single-user system
- Built-in calendar UI — events are stored and surfaced, not visually scheduled
- Real-time notifications in v1 — reminders surface in the daily briefing only
- Mobile-native app — PWA installation covers mobile and desktop

---

## 4. Target user

A developer-student hybrid who simultaneously manages professional projects, academic deliverables, and personal commitments. Comfortable with technical tools but frustrated by the overhead of keeping them organized. Prefers to be told what to do next rather than asked questions. Values speed of capture and quality of reasoning over visual polish.

---

## 5. System architecture

### 5.1 Layers

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js + Tailwind CSS (PWA) | Chat UI + sidebar panel + offline capture |
| Backend core | FastAPI (async) | AI orchestration, RAG engine, ingestion endpoint. Paralelismo via `asyncio.gather` para operaciones I/O-bound |
| LLM provider | DeepSeek API via `LLMProvider` interface | Classification (fast model) + RAG reasoning (full model) |
| Embedding provider | Qwen3-Embedding-8B via `EmbeddingProvider` interface | Embeddings de 1536 dims vía DeepInfra/OpenRouter ($0.01/M tokens) |
| Database | Supabase (Postgres + pgvector + Realtime + Auth) | All persistent data + semantic embeddings (vector(1536)) + live sidebar updates |
| Integrations | Microservices in Docker (Python) | Connectors HTTP → `/ingest` directamente. Sin cola de mensajes en MVP |
| Observability | Prometheus + Grafana | Latency, error rate, AI response time, events processed per connector |

### 5.2 Provider interfaces

Tanto el LLM como el embedding están desacoplados detrás de interfaces abstractas. Cambiar de proveedor requiere únicamente una nueva implementación — sin tocar lógica de negocio.

```
LLMProvider (abstract)
└── DeepSeekProvider (default)
    ├── classifier → deepseek-chat (fast, low cost)
    └── reasoner  → deepseek-reasoner (full model)

EmbeddingProvider (abstract)
└── QwenEmbeddingProvider (default)
    └── Qwen3-Embedding-8B via DeepInfra · 1536 dims · $0.01/M tokens
```

### 5.3 Data flow — capture

1. User types anything in the chat input
2. Next.js sends the message to FastAPI via `POST /chat`
3. FastAPI ejecuta en paralelo con `asyncio.gather`:
   - `classify()` → deepseek-chat detecta tipo y extrae campos
   - `embed()` → Qwen3-Embedding-8B genera el vector de 1536 dims
4. Escribe el record en la tabla correspondiente de Supabase con su embedding
5. Retorna confirmación al chat en < 2 segundos
6. Supabase Realtime actualiza el sidebar sin reload

### 5.4 Data flow — query

1. User asks a question in the chat
2. FastAPI genera el embedding de la pregunta (1536 dims)
3. Busca en pgvector los registros más semánticamente relevantes en todas las tablas
4. Pasa el contexto recuperado + la pregunta al reasoner (deepseek-reasoner)
5. Retorna una respuesta fundamentada — sin hallucination, solo datos del usuario

### 5.5 Data flow — offline capture

1. El service worker detecta que no hay conexión
2. El mensaje se guarda como **texto crudo** en IndexedDB — sin clasificar ni embedear
3. El sidebar muestra un badge "N capturas pendientes de sincronizar"
4. Al reconectarse, FastAPI procesa la cola en orden: clasifica, embeda, crea el record
5. Todo el procesamiento ocurre en sync, nunca offline

### 5.6 Data flow — integration connector

1. El conector (e.g. `github-connector`) recibe un webhook o hace polling
2. Normaliza los datos al schema interno (task, note, event, o reminder)
3. Llama directamente a `POST /ingest` en FastAPI via HTTP
4. FastAPI clasifica, embeda, y guarda el record en Supabase
5. El record es indistinguible de una captura manual

> **Nota:** Redis como cola de mensajes entre connectors y FastAPI es un upgrade documentado para cuando el volumen justifique desacople ante caídas o backpressure. No aplica en MVP de uso personal.

---

## 6. Data model

### `users`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key, from Supabase Auth |
| name | text | Display name |
| timezone | text | IANA timezone string |
| preferences | jsonb | Extensible preferences object |
| created_at | timestamptz | Auto-set |

### `projects`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid | FK → users |
| name | text | e.g. InfraPilot, ESCOM, CIC, Personal |
| color | text | Hex color for sidebar display |
| context | text | Free-text description the AI uses for classification |
| is_active | boolean | Inactive projects hidden from daily briefing |

### `tasks`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| project_id | uuid | FK → projects |
| title | text | Extracted or written by AI from the raw capture |
| description | text | Optional detail |
| status | enum | `pending` \| `in_progress` \| `done` \| `cancelled` |
| priority | integer | 1–5, calculated by AI or set manually |
| energy_level | enum | `low` \| `medium` \| `high` — cognitive load of the task |
| deadline | timestamptz | Optional |
| context_note | text | AI-maintained memory: blockers, decisions, last state. Se actualiza solo cuando el usuario menciona la tarea y aporta información de estado nueva |
| source | text | `manual` \| `github` \| `gmail` \| `calendar` \| etc. |
| embedding | vector(1536) | Qwen3-Embedding-8B · pgvector |
| created_at | timestamptz | Auto-set |
| updated_at | timestamptz | Auto-updated |

### `events`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| project_id | uuid | FK → projects (nullable) |
| title | text | Event name |
| starts_at | timestamptz | Start datetime |
| duration_min | integer | Duration in minutes |
| type | enum | `meeting` \| `class` \| `appointment` \| `other` |
| recurrence | jsonb | RRULE or null |
| source | text | `manual` \| `google_calendar` \| etc. |
| embedding | vector(1536) | Qwen3-Embedding-8B · pgvector |

### `reminders`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| project_id | uuid | FK → projects (nullable) |
| title | text | What to remember |
| due_at | timestamptz | When it fires |
| amount | decimal | Optional — for payments |
| currency | text | Optional — ISO 4217 code |
| recurrence | jsonb | RRULE or null |
| is_done | boolean | Marked when acknowledged |

### `notes`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| project_id | uuid | FK → projects (nullable) |
| content | text | Raw content — decisions, links, ideas, references |
| tags | text[] | AI-extracted keywords |
| source | text | `manual` \| `github` \| `gmail` \| etc. |
| embedding | vector(1536) | Qwen3-Embedding-8B · pgvector |
| created_at | timestamptz | Auto-set |

### `conversations`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid | FK → users |
| role | enum | `user` \| `assistant` |
| content | text | Raw message content |
| metadata | jsonb | Records created/modified en este turno — usado para corrección de misclasificación |
| embedding | vector(1536) | Qwen3-Embedding-8B · pgvector |
| created_at | timestamptz | Auto-set |

### `briefings`

| Field | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid | FK → users |
| date | date | Un briefing por día-calendario |
| content | text | Contenido generado por el reasoner |
| invalidated_at | timestamptz | Nullable — se invalida si el usuario captura algo con > 30 min de debounce tras verlo |
| created_at | timestamptz | Auto-set |

---

## 7. Features — MVP scope

### 7.1 Natural language capture

A single input field always visible at the bottom of the chat. The user types anything in plain language. The AI determines the record type and creates the appropriate entry with no additional prompts.

- `'fix the NETCONF rollback bug in InfraPilot'` → task linked to InfraPilot
- `'junta con Alex mañana a las 3 sobre el checkpoint de InfraPilot'` → event linked to InfraPilot
- `'pagar colegiatura el viernes $3,200'` → reminder in Personal
- `'decidimos usar pgvector en lugar de Pinecone'` → note linked to ARIA

Response time target: under 2 seconds from send to confirmation in chat.

### 7.2 Misclassification correction

Si el clasificador se equivoca, el usuario corrige en lenguaje natural:

- `'eso era un evento, no una tarea'`
- `'ese reminder es de InfraPilot, no Personal'`

El assistant detecta la intención de corrección usando el `metadata` del turno anterior, hace el fix en Supabase, y confirma. No se requiere ningún comando especial ni UI adicional.

### 7.3 Daily briefing

Computado automáticamente al abrir la app. Cacheado en la tabla `briefings` — si ya existe uno para el día actual se sirve sin llamar al reasoner. Se invalida y regenera únicamente si el usuario captura algo nuevo con debounce de 30 minutos. Costo real: 1 llamada al reasoner por día en condiciones normales.

Contiene:

- **Una tarea recomendada** — elegida cruzando deadlines, energy level, antigüedad por proyecto, y eventos del día
- **Eventos de hoy** — ordenados cronológicamente
- **Reminders** venciendo hoy o mañana
- **Una línea de resumen** por proyecto activo

El briefing es un mensaje del assistant en el chat, no un widget separado.

### 7.4 Contextual question answering

El usuario pregunta cualquier cosa sobre sus datos. RAG fundamenta la respuesta en registros reales — el AI no inventa información.

- `'¿en qué quedé con el servicio social del CIC?'`
- `'¿cuándo vence mi próximo pago?'`
- `'¿qué tareas de InfraPilot tienen deadline esta semana?'`

### 7.5 Sidebar panel

Panel derecho persistente con el estado actual del knowledge base. Actualizado en tiempo real via Supabase Realtime. Read-only — toda interacción ocurre desde el chat. Contiene:

- Proyectos activos con conteo de tareas y última actividad
- Tareas agrupadas por proyecto, filtrables por status
- Eventos próximos (7 días)
- Reminders pendientes

### 7.6 Offline capture

El service worker intercepta capturas sin conexión. Guarda texto crudo en IndexedDB. Al reconectarse, FastAPI procesa la cola en orden. El sidebar muestra un badge con las capturas pendientes.

---

## 8. Integration layer — connectors

Cada conector es un microservicio Python independiente en su propio contenedor Docker. En MVP llaman directamente a `POST /ingest` en FastAPI via HTTP sin cola intermedia.

### 8.1 Connector interface contract

- Escucha un webhook o hace polling a una API externa
- Normaliza los datos al schema interno (task, note, event, o reminder)
- Setea el campo `source` con el nombre del conector
- Llama `POST /ingest` en FastAPI con el payload normalizado
- Expone `GET /metrics` en formato Prometheus text
- Expone `GET /health` retornando `{"status": "ok"}`

### 8.2 MVP connectors

| Connector | Trigger | Records created |
|---|---|---|
| `github-connector` | Issue opened / PR opened / comment | task (issue) or note (PR comment) |
| `gmail-connector` | New email matching project keywords | note with sender and subject |
| `calendar-connector` | Google Calendar event created/updated | event |

---

## 9. AI design

### 9.1 LLMProvider interface

FastAPI interactúa con modelos de lenguaje exclusivamente a través de una interfaz abstracta `LLMProvider`. DeepSeek es la implementación default. Cambiar a Anthropic, OpenAI u Ollama requiere solo una nueva implementación — sin cambios en lógica de negocio.

### 9.2 EmbeddingProvider interface

FastAPI interactúa con el modelo de embeddings exclusivamente a través de una interfaz abstracta `EmbeddingProvider`. La implementación default es Qwen3-Embedding-8B via DeepInfra, con dimensión fija de **1536 dims**.

`EMBEDDING_DIM = 1536` es la única fuente de verdad — usada en la definición del índice pgvector y en todas las operaciones de búsqueda.

**Por qué 1536:** los registros de ARIA son texto corto. MRL garantiza que el prefijo de 1536 dims del vector de 4096 retiene la mayor parte de la información semántica. Si en fases futuras ARIA embeda documentos largos, se planifica migración del índice en ese momento.

### 9.3 Two-model strategy

| Role | Model | Used for |
|---|---|---|
| Classifier | `deepseek-chat` | Clasificación de input, extracción de campos, detección de correcciones, detección de trigger para context_note |
| Reasoner | `deepseek-reasoner` | Respuestas RAG, generación del briefing, actualización de context_note |

### 9.4 Parallelism strategy

Las operaciones I/O-bound en el flujo de captura se ejecutan con `asyncio.gather` — el approach nativo de FastAPI para concurrencia sin overhead de procesos:

```python
result, embedding = await asyncio.gather(
    classify(message),
    embed(message)
)
```

Lo mismo aplica en la generación del briefing: las consultas a `tasks`, `events`, `reminders`, y `notes` se ejecutan en paralelo antes de llamar al reasoner.

### 9.5 context_note update trigger

El campo `context_note` se actualiza únicamente cuando:
1. El clasificador detecta que el mensaje se refiere a una tarea existente, **Y**
2. El mensaje contiene información de estado nueva — blocker, decisión, avance, o actualización explícita

No se actualiza en menciones pasivas ni durante el briefing. Estimado: ~5-10% de los mensajes. Cada actualización llama al reasoner con el `context_note` actual + el nuevo mensaje.

### 9.6 Prompt structure

- System prompt: nombre del usuario, proyectos activos con su `context`, datetime actual y timezone
- Contexto RAG: inyectado entre el system prompt y el mensaje del usuario
- Historial: últimos 20 turnos de `conversations`
- El assistant está instruido para ser directo, no hacer preguntas de clarificación, y siempre actuar sobre input ambiguo

---

## 10. Observability

Cada servicio expone `/metrics` en formato Prometheus text. Grafana provee dashboards. Alertas para error rate > 5% y latencia p95 > 3 segundos.

| Metric | Service | Description |
|---|---|---|
| `aria_chat_latency_seconds` | FastAPI | Tiempo de respuesta end-to-end del chat |
| `aria_classification_latency_seconds` | FastAPI | Tiempo de respuesta del clasificador |
| `aria_embedding_latency_seconds` | FastAPI | Tiempo de generación de embedding |
| `aria_rag_latency_seconds` | FastAPI | Retrieval pgvector + respuesta del reasoner |
| `aria_records_created_total` | FastAPI | Records creados por type y source |
| `aria_briefing_cache_hits_total` | FastAPI | Briefings desde cache vs regenerados |
| `aria_context_note_updates_total` | FastAPI | Actualizaciones de context_note |
| `aria_connector_events_total` | Each connector | Eventos procesados por conector |
| `aria_connector_errors_total` | Each connector | Errores por conector |
| `aria_offline_queue_depth` | Frontend | Capturas pendientes en IndexedDB |

---

## 11. Build plan

| Phase | Name | Deliverables |
|---|---|---|
| 0 | Foundations | Supabase schema + pgvector (vector(1536)), FastAPI skeleton con `LLMProvider` y `EmbeddingProvider` interfaces, Next.js PWA shell, Supabase Auth |
| 1 | Core loop | Captura en lenguaje natural, `asyncio.gather` para clasificación + embedding en paralelo, creación de records, corrección de misclasificación, chat UI, sidebar con Realtime |
| 2 | Memory & RAG | Pipeline de embeddings Qwen3, búsqueda pgvector, Q&A contextual, `context_note` updates, historial de conversación |
| 3 | Daily briefing | Generación del briefing, algoritmo de recomendación de tarea, cache con tabla `briefings`, debounce de invalidación |
| 4 | Connectors | Endpoint `/ingest`, `github-connector`, `gmail-connector`, `calendar-connector` — HTTP directo sin cola |
| 5 | Observability | Métricas Prometheus en todos los servicios, dashboards Grafana, alertas |
| 6 | Offline & polish | Service worker, cola IndexedDB, sync al reconectarse, PWA install manifest |

---

## 12. Cost estimate

Estimado mensual para uso personal: 8 proyectos activos, 9 capturas/día, 5 preguntas/día.

| Component | Monthly cost |
|---|---|
| Qwen3-Embedding-8B (DeepInfra) | ~$0.0003 |
| DeepSeek classifier (deepseek-chat) | ~$0.10 |
| DeepSeek reasoner (deepseek-reasoner) | ~$0.70 |
| **Total estimado** | **< $1 USD/mes** |

---

## 13. Future upgrades

- **Redis como cola de mensajes** — upgrade cuando el volumen de connectors justifique desacople ante caídas de FastAPI o backpressure. No aplica en MVP
- **Push notifications** — requiere notification service; diferido a post-MVP
- **File attachments** — Supabase Storage listo; al incorporar PDFs evaluar migración del índice a 4096 dims
- **Mobile voice capture** — input por voz para captura sin escribir
- **Agent mode** — ARIA crea tareas proactivamente detectando patrones
- **Sharing** — exportar snapshot de proyecto o compartir briefing

---

*ARIA — Personal AI Operating System · PRD v1.2.0*