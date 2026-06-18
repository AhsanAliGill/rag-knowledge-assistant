# Knowledge Assistant


### A production-grade, full-stack RAG application — upload PDFs as an admin, let your team ask natural-language questions against them with real-time streamed answers.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-336791?logo=postgresql&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-FF3E00)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C)
![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Llama--3.3--70B-F55036)
![Cohere](https://img.shields.io/badge/Reranker-Cohere-6B4FBB)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

1. [Overview](#-overview)
2. [AI Core & Architecture](#-ai-core--architecture)
3. [Full System Flow Diagram](#-full-system-flow-diagram)
4. [Tech Stack](#-tech-stack)
5. [Project Directory Structure](#-project-directory-structure)
6. [Getting Started — Docker](#-getting-started--docker-recommended)
7. [Getting Started — Manual](#-getting-started--manual-development)
8. [Environment Variables](#-environment-variables)
9. [Role-Based Access Control](#-role-based-access-control)
10. [API Endpoints](#-api-endpoints)
11. [Security & Cost Control](#-security--cost-control)
12. [Design Decisions](#-design-decisions)
13. [Scalability Considerations](#-scalability-considerations)

---

## 🗺 Overview

Knowledge Assistant is a **full-stack RAG (Retrieval-Augmented Generation) platform** that lets organisations build a private, conversational knowledge base from their PDF documents.

| Persona | What they can do |
|---|---|
| **Admin** | Upload PDFs, delete documents, view the document library |
| **User** | Chat with the knowledge base, browse conversation history, run RAGAS evaluations |

A single **shared document corpus** means every PDF an admin uploads is instantly queryable by all authenticated users — no per-user silos.

Key capabilities at a glance:

- **Streaming chat** — answers stream token-by-token via NDJSON; no waiting for the full response
- **Hybrid retrieval** — dense (Qdrant) + sparse (BM25) fused with RRF, then cross-encoder reranked by Cohere
- **Inline citations** — every answer cites exact page numbers from the source PDFs
- **Conversation memory** — multi-turn context with automatic history compression
- **RAGAS evaluation** — automated quality scoring (faithfulness, relevancy, precision, recall)
- **Live reload dev** — bind-mounted volumes in Docker so code changes reflect instantly without rebuilds

---

## 🧠 AI Core & Architecture

### What the Pipeline Does

| Capability | Implementation |
|---|---|
| **Document Parsing** | PyMuPDF parses PDFs into per-page `Document` objects with normalised 1-based page numbers |
| **Hierarchical Chunking** | Parent chunks (2000 tokens) for context expansion; child chunks (500 tokens, 100-token overlap) for precise retrieval |
| **Table Preservation** | Table elements are stored as a single unsplit child chunk to prevent row/column leakage across chunk boundaries |
| **Semantic Embedding** | `openai/text-embedding-3-large` (3072-dim) via OpenRouter — fully OpenAI-compatible |
| **Keyword Search** | BM25Okapi index (rank-bm25) persisted as `shared.pkl` for the shared corpus |
| **Hybrid Retrieval** | `EnsembleRetriever`: 60% dense (Qdrant cosine) + 40% sparse (BM25), fused with Reciprocal Rank Fusion |
| **Cross-Encoder Reranking** | Cohere `rerank-english-v3.0` re-scores the fused pool, returning the top-N most relevant chunks |
| **Query Rewriting** | LLM resolves pronouns and conversation references into self-contained standalone questions |
| **No-Retrieval Routing** | Chitchat, greetings, and meta-questions about the conversation are answered directly from history without hitting the vector DB |
| **History Compression** | When conversation history exceeds ~3000 tokens, older turns are summarised and replaced with a single summary message |
| **Streaming Generation** | Groq `llama-3.3-70b-versatile` streams tokens via NDJSON; frontend renders them in real-time |
| **RAGAS Evaluation** | Automated quality scoring: faithfulness, answer relevancy, context precision, context recall |

### LLM & AI Provider Breakdown

| Role | Provider | Model |
|---|---|---|
| Answer Generation (streaming) | **Groq** (free tier) | `llama-3.3-70b-versatile` |
| Query Rewriting | **Groq** (free tier) | `llama-3.3-70b-versatile` |
| History Summarisation | **Groq** (free tier) | `llama-3.3-70b-versatile` |
| Text Embeddings | **OpenRouter** → OpenAI | `text-embedding-3-large` (3072-dim) |
| Cross-Encoder Reranking | **Cohere** | `rerank-english-v3.0` |
| RAG Evaluation | **RAGAS** + HuggingFace Datasets | faithfulness, relevancy, precision, recall |

---

## 🏗 Full System Flow Diagram

### Ingestion Pipeline (background job after upload)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                           │
└─────────────────────────────────────────────────────────────────────┘

 [Admin: POST /api/v1/rag/documents]
      │  validate: size ≤ 50 MB, extension .pdf, SHA-256 dedup
      ▼
 [PyMuPDF Parser]
      │  → per-page Document objects
      │  → normalize 0-based page → 1-based page_number
      │  → drop header/footer boilerplate (regex)
      ▼
 [HierarchicalChunker]
      │  → parent chunks  (full page/section, 2000 tokens)
      │  → child chunks   (500 tokens, 100 overlap, tiktoken cl100k_base)
      │  → tables         (single unsplit child chunk)
      ▼
 [MetadataTagger]
      │  → attach: doc_id, chunk_id, parent_id,
      │            chunk_type, section_path, page_num
      │            namespace = "shared"  ← all admin docs share one corpus
      ▼
      ├──────────────────────────┬─────────────────────────┐
      ▼                          ▼                         │
 [EmbeddingEngine]          [BM25Indexer]                  │
  OpenRouter → OpenAI        BM25Okapi.build()             │
  text-embedding-3-large     serialize → shared.pkl        │
  batch=100, concurrency=5                                 │
      │                          │  ◄── asyncio.gather() ──┘
      ▼                          ▼
 [VectorIndexer]           [DB: save chunks]
  Qdrant upsert              PostgreSQL rag_chunks
  cosine, 3072-dim           asyncio.gather() parallel
  namespace = "shared"
      │
      ▼
 [Mark doc status = READY, update job progress → 100%]
```

### Query Pipeline (any authenticated user)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         QUERY PIPELINE                              │
└─────────────────────────────────────────────────────────────────────┘

 [POST /api/v1/rag/query/stream]
      │  JWT auth → extract user_id
      │  validate question (non-empty, ≤ 1000 chars)
      ▼
 [Load/Create Conversation]
      │  history = last 20 messages from rag_conversation_messages
      ▼
 [History Compression]  ← if history tokens > 3000
      │  older turns → LLM summariser → single summary message
      │  last 6 messages kept verbatim
      ▼
 [Query Rewriter]  (skipped on first message)
      │  LLM: resolve pronouns, carry context from prior turns
      │  → standalone question  OR  [NO_RETRIEVAL] signal
      ▼
      ├─── [NO_RETRIEVAL] ──► LLM answers from history ──► stream tokens
      │
      ▼ (standalone question)
      ├──────────────────────────────────────┐
      ▼                                      ▼
 [Dense Retriever]                     [Sparse Retriever]
  Qdrant cosine similarity               BM25Okapi keyword search
  filter: namespace = "shared"           from shared.pkl
  k = 20 candidates                      k = 20 candidates
      │                                      │
      └──────────────┬───────────────────────┘
                     ▼
            [EnsembleRetriever]
             RRF Fusion: 60% dense + 40% BM25
                     │
                     ▼
            [Cohere Cross-Encoder Reranker]
             rerank-english-v3.0
             top_n = 8 chunks
                     │
                     ▼
            [Sort by chunk_id sequence]
             (restores document reading order)
                     │
                     ▼
            [Groq LLM — llama-3.3-70b-versatile]
             stream tokens → NDJSON events
             cite page numbers inline (Page N)
                     │
                     ▼
 [Persist conversation messages after stream completes]
                     │
                     ▼
 [NDJSON stream: start → meta → token* → done]
```

---

## 🛠 Tech Stack

### Backend

| Technology | Purpose | Version |
|---|---|---|
| **FastAPI** | Async REST API framework | ≥ 0.136 |
| **SQLModel** | ORM (SQLAlchemy + Pydantic hybrid) | ≥ 0.0.38 |
| **asyncpg** | Async PostgreSQL driver | ≥ 0.31 |
| **Alembic** | Database schema migrations | ≥ 1.18 |
| **python-jose** | JWT creation & decoding | ≥ 3.5 |
| **bcrypt / passlib** | Password hashing | latest |
| **LangChain** | RAG orchestration framework | ≥ 0.3 |
| **langchain-openai** | Embeddings via OpenRouter | ≥ 0.2 |
| **langchain-groq** | LLM inference (streaming) | ≥ 1.1 |
| **langchain-cohere** | Cross-encoder reranking | ≥ 0.3 |
| **langchain-qdrant** | Qdrant vector store integration | ≥ 0.2 |
| **langchain-classic** | EnsembleRetriever, ContextualCompression | bundled |
| **Qdrant** | Vector database (cosine, 3072-dim) | ≥ 1.12 |
| **rank-bm25** | BM25Okapi sparse retrieval | ≥ 0.2.2 |
| **PyMuPDF** | PDF parsing | ≥ 1.24 |
| **tiktoken** | Token counting for chunking | ≥ 0.8 |
| **RAGAS** | RAG evaluation metrics | ≥ 0.2 |
| **uv** | Python package manager & runner | latest |
| **pytest + xdist** | Parallel integration testing | ≥ 9.0 / ≥ 3.6 |

### Frontend

| Technology | Purpose | Version |
|---|---|---|
| **React 18** | UI component library | 18 |
| **TypeScript** | Type-safe development | 5 |
| **TanStack Start** | Full-stack React meta-framework (SSR-ready) | ≥ 1.167 |
| **TanStack Router** | File-based routing with `beforeLoad` guards | ≥ 1.168 |
| **Vite** | Build tool + HMR dev server | ≥ 6 |
| **Tailwind CSS** | Utility-first styling | ≥ 4 |
| **Lucide React** | Icon library | latest |
| **Sonner** | Toast notifications | latest |
| **Zod** | Runtime schema validation | latest |

### Infrastructure

| Technology | Purpose |
|---|---|
| **Docker Compose** | Orchestrates backend + frontend with bind-mounted live reload |
| **PostgreSQL 14+** | Primary relational database |
| **Qdrant Cloud** | Hosted vector database |

---

## 📁 Project Directory Structure

```
task/
├── .env.example              # root compose variable (VITE_API_URL)
├── docker-compose.yml        # full-stack orchestration
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml        # dependencies, pytest config, ruff linting
│   ├── .env.example          # all backend environment variable templates
│   ├── alembic/              # database migration scripts
│   │   └── versions/
│   │       └── a1b2c3d4e5f6_add_role_to_users.py  # RBAC + admin seed user
│   └── src/app/
│       ├── main.py           # FastAPI app, CORS, router registration, lifespan
│       ├── dependencies.py   # get_current_active_user, require_admin
│       │
│       ├── core/
│       │   ├── config.py     # app-level settings (DB URL, SECRET_KEY, CORS)
│       │   └── security.py   # bcrypt hashing, JWT encode/decode
│       │
│       ├── models/
│       │   ├── user.py       # User + UserRole enum (admin | user)
│       │   ├── document.py   # RAGDocument (status, sha256, storage_path)
│       │   ├── chunk.py      # RAGChunk (parent/child, vector_id, page_num)
│       │   ├── ingestion_job.py # RAGIngestionJob (state machine, progress %)
│       │   ├── conversation.py  # RAGConversation + RAGConversationMessage
│       │   └── evaluation.py    # RAGEvaluation + RAGEvaluationResult
│       │
│       ├── schemas/
│       │   ├── auth.py       # UserRegister, Token, UserRead (includes role)
│       │   ├── query.py      # QueryRequest, QueryResponse, SourceChunk
│       │   ├── document.py   # DocumentUploadResponse, JobStatusResponse, etc.
│       │   ├── conversation.py
│       │   └── evaluation.py
│       │
│       ├── routers/
│       │   ├── auth.py         # /api/v1/auth/*
│       │   ├── documents.py    # /api/v1/rag/documents/* (upload/delete: admin only)
│       │   ├── query.py        # /api/v1/rag/query + /stream
│       │   ├── evaluation.py   # /api/v1/rag/evaluations/*
│       │   └── conversations.py
│       │
│       ├── controllers/
│       │   ├── auth.py
│       │   ├── document_controller.py   # upload, list (all docs), delete
│       │   ├── query_controller.py      # conversation management, pipeline call
│       │   ├── evaluation_controller.py
│       │   └── conversation_controller.py
│       │
│       └── services/rag/
│           ├── pipeline.py              # RAGPipeline orchestrator
│           ├── ingestion/               # parse → chunk → embed → index
│           ├── retrieval/               # dense + sparse + rerank
│           ├── generation/              # LLM client, prompts, history compression
│           └── evaluation/              # RAGAS runner + metrics
│
└── frontend/
    ├── Dockerfile.dev        # lightweight dev image (npm run dev with HMR)
    ├── vite.config.ts
    ├── package.json
    └── src/
        ├── routes/
        │   ├── _app.tsx             # root layout + JWT auth guard (beforeLoad)
        │   ├── _app.dashboard.tsx   # stat cards + recent docs/conversations
        │   ├── _app.chat.tsx        # streaming chat with conversation sidebar
        │   ├── _app.documents.tsx   # document library — admin only (beforeLoad guard)
        │   ├── _app.conversations.tsx
        │   ├── _app.evaluations.tsx
        │   ├── _app.settings.tsx
        │   ├── login.tsx
        │   └── register.tsx
        │
        ├── components/
        │   ├── AppSidebar.tsx       # role-aware nav (Documents link: admin only)
        │   └── StatusBadge.tsx
        │
        └── lib/api/
            ├── auth.ts              # login, register, logout (stores role in localStorage)
            ├── documents.ts         # upload (multipart), list, delete, job poll
            ├── query.ts             # streamQuery — NDJSON async generator
            ├── conversations.ts
            └── evaluations.ts
```

---

## 🐳 Getting Started — Docker (Recommended)

Docker Compose runs **both services** with live-reload: edit any backend `.py` or frontend `.tsx` file and changes reflect instantly.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys for Groq, OpenRouter, Cohere, and Qdrant Cloud (all have free tiers)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd task
```

### 2. Configure environment variables

```bash
# Root-level (frontend API URL)
cp .env.example .env

# Backend secrets
cp backend/.env.example backend/.env
# Open backend/.env and fill in all API keys
```

### 3. Build and start

```bash
docker compose up --build -d
```

| Service | URL |
|---|---|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

### 4. Run database migrations

On first start, run migrations to create all tables and seed the admin user:

```bash
docker compose exec backend uv run alembic upgrade head
```

### 5. Log in

The migration seeds a default admin account:

| Field | Value |
|---|---|
| Email | `ahs462agk@gmail.com` |
| Password | `462195agk` |
| Role | `admin` |

> ⚠️ Change these credentials in production.

### Common commands

```bash
# Tail logs from both services
docker compose logs -f

# Rebuild after adding a new dependency
docker compose up --build -d

# Stop everything
docker compose down

# Stop and wipe all volumes (uploads, BM25 indexes)
docker compose down -v
```

---

## 💻 Getting Started — Manual Development

If you prefer running services directly on your machine:

### Backend

```bash
cd backend

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Fill in all values

# Run migrations
uv run alembic upgrade head

# Start dev server with live reload
uv run uvicorn app.main:app --reload --reload-dir src
# API live at http://localhost:8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
# UI live at http://localhost:3000
```

### Running Tests

```bash
cd backend

# All tests in parallel
uv run pytest

# Verbose output, single file
uv run pytest -v tests/test_auth.py

# Filter by name
uv run pytest -k "test_register"
```

> Tests use `TEST_DATABASE_URL`. Each parallel worker gets its own PostgreSQL schema (`test_gw0`, `test_gw1`, …) for full isolation.

---

## 🔑 Environment Variables

### Root `.env` (docker compose only)

```env
# URL the browser uses to call the backend
VITE_API_URL=http://localhost:8000
```

### `backend/.env`

```env
# ── Application ───────────────────────────────────────────────────────────────
APP_NAME="Knowledge Assistant"
DEBUG=false

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/knowledge_db
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/knowledge_db_test

# ── Auth ──────────────────────────────────────────────────────────────────────
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

CORS_ORIGINS=["http://localhost:3000"]

# ── Groq — LLM Generation & Rewriting (free tier) ────────────────────────────
GROQ_API_KEY=gsk_your-groq-key-here
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=1024

# ── OpenRouter — Embeddings ───────────────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-your-openrouter-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_MODEL=openai/text-embedding-3-large
EMBEDDING_DIMENSIONS=3072
EMBEDDING_BATCH_SIZE=100

# ── Qdrant Cloud — Vector Database ───────────────────────────────────────────
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key-here
QDRANT_COLLECTION=rag_documents

# ── Cohere — Reranking ────────────────────────────────────────────────────────
COHERE_API_KEY=your-cohere-api-key-here
COHERE_RERANK_MODEL=rerank-english-v3.0

# ── RAG Retrieval Tuning ──────────────────────────────────────────────────────
RAG_DENSE_K=20
RAG_SPARSE_K=20
RAG_DENSE_WEIGHT=0.6
RAG_RERANK_TOP_N=8
RAG_RELEVANCE_THRESHOLD=0.25
RAG_CONTEXT_TOKEN_BUDGET=3500

# ── Chunking ──────────────────────────────────────────────────────────────────
PARENT_CHUNK_SIZE=2000
CHILD_CHUNK_SIZE=500
CHILD_CHUNK_OVERLAP=100

# ── File Upload ───────────────────────────────────────────────────────────────
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=50
MAX_PAGES=500
MAX_UPLOADS_PER_DAY=10
BM25_INDEX_DIR=bm25_indexes
GROUND_TRUTH_DIR=ground_truth
```

---

## 🔐 Role-Based Access Control

The system has two roles: **admin** and **user**.

### What each role can do

| Action | Admin | User |
|---|---|---|
| Upload documents | ✅ | ❌ 403 |
| Delete documents | ✅ | ❌ 403 |
| View document library (`/documents`) | ✅ | ❌ redirected to dashboard |
| Chat / query the knowledge base | ✅ | ✅ |
| View conversation history | ✅ | ✅ |
| Run RAGAS evaluations | ✅ | ✅ |

### How it works

**Backend** — `require_admin` FastAPI dependency on upload and delete endpoints:
```python
async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(403, "Admin access required.")
    return current_user
```

**Frontend** — `beforeLoad` guard on the `/documents` route:
```typescript
beforeLoad: () => {
  const user = JSON.parse(localStorage.getItem("user") ?? "null");
  if (user?.role !== "admin") throw redirect({ to: "/dashboard" });
}
```

**Sidebar** — Documents link is filtered out for non-admin users automatically.

### Shared document corpus

All admin-uploaded documents are indexed under the `"shared"` namespace in Qdrant. Every user's queries search this shared namespace — there are no per-user document silos. The admin manages the corpus; all users benefit from it.

### Creating additional admin users

Run the migration SQL directly, or register a user and update their role:

```sql
UPDATE users SET role = 'admin' WHERE email = 'newadmin@example.com';
```

---

## 🔌 API Endpoints

All endpoints are prefixed with `/api/v1`. Protected routes require `Authorization: Bearer <token>`.

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | No | Create a new user account (role defaults to `user`) |
| `POST` | `/auth/login` | No | Login — returns JWT + user object with `role` field |
| `GET` | `/auth/me` | Yes | Get current user profile |

**Login response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "username": "alice",
    "email": "alice@example.com",
    "is_active": true,
    "role": "user"
  }
}
```

---

### Document Management

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/rag/documents` | Admin only | Upload PDF — starts background ingestion job |
| `GET` | `/rag/documents` | Any user | List all documents in the shared corpus (paginated) |
| `GET` | `/rag/documents/{doc_id}` | Any user | Get document details + chunk counts |
| `DELETE` | `/rag/documents/{doc_id}` | Admin only | Delete document + vectors + BM25 index entries |
| `POST` | `/rag/documents/{doc_id}/ground-truth` | Any user | Upload Q&A pairs for RAGAS evaluation |
| `GET` | `/rag/documents/jobs/{job_id}` | Any user | Poll ingestion job progress (0–100%) |

**Upload (multipart/form-data):**
```
POST /api/v1/rag/documents
Content-Type: multipart/form-data
Body: file=<pdf>, description="optional text"

Response 202:
{
  "doc_id": "uuid",
  "job_id": "uuid",
  "status": "queued",
  "message": "Document accepted. Use job_id to track ingestion progress."
}
```

**Job status:**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "progress": 50,
  "message": "Embedding 1240 chunks + building keyword index...",
  "error_message": null
}
```

---

### AI Query

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/rag/query` | Any user | Ask a question — returns full response when complete |
| `POST` | `/rag/query/stream` | Any user | Ask a question — streams NDJSON tokens in real-time |

**Request (both endpoints):**
```json
{
  "question": "What is the annual leave policy?",
  "conversation_id": null
}
```

**Streaming response (NDJSON — one JSON object per line):**
```
{"type": "start", "conversation_id": "uuid"}
{"type": "meta", "sources": [...], "query_id": "a1b2c3d4", "chunks_retrieved": 8}
{"type": "token", "content": "Full"}
{"type": "token", "content": "-time"}
{"type": "token", "content": " employees..."}
{"type": "done", "latency_ms": 1843}
```

---

### Conversations

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/rag/conversations` | Any user | List all conversations |
| `GET` | `/rag/conversations/{id}` | Any user | Get full message history |
| `DELETE` | `/rag/conversations/{id}` | Any user | Delete conversation and all its messages |

---

### RAGAS Evaluation

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/rag/evaluations` | Any user | Trigger RAGAS evaluation for a document |
| `GET` | `/rag/evaluations/{eval_id}` | Any user | Get evaluation status and scores |
| `GET` | `/rag/evaluations` | Any user | List all evaluation runs |

**Evaluation results:**
```json
{
  "eval_id": "uuid",
  "status": "completed",
  "faithfulness": 0.91,
  "answer_relevancy": 0.88,
  "context_precision": 0.85,
  "context_recall": 0.79,
  "overall": 0.86,
  "qa_done": 20
}
```

---

### Health

```
GET /health  →  {"status": "ok"}
```

---

## 🛡 Security & Cost Control

### Authentication & Authorization

- All `/rag/*` endpoints require a valid **HS256 JWT** in `Authorization: Bearer`.
- Tokens are decoded via `python-jose`; expired or tampered tokens return `401`.
- Passwords are hashed with **bcrypt** — never stored in plaintext.
- Role (`admin` / `user`) is embedded in the `UserRead` schema and stored in the browser's `localStorage` for UI gating. The backend always re-checks role server-side — frontend gating is UI-only.

### Upload Safeguards

| Limit | Value |
|---|---|
| Max file size | 50 MB |
| Accepted types | `.pdf` only |
| Max pages | 500 pages |
| Duplicate prevention | SHA-256 hash (per shared corpus) |
| Daily upload limit | 10 per day (configurable) |

### AI Cost Control

- **LLM context budget**: Capped at `RAG_CONTEXT_TOKEN_BUDGET=3500` tokens — only top-reranked chunks within budget reach the LLM.
- **Embedding batching**: Batches of 100 chunks with a semaphore limiting concurrency to 5 parallel API calls.
- **Groq free tier**: Generation LLM has no per-token charges.
- **History compression**: Conversations > ~3000 tokens are auto-compressed to a summary + last 6 messages before each LLM call.

### Error Handling

- **Qdrant 404 (no collection / no documents)**: Returns `HTTP 400` — `"No documents found. Please upload a document before querying."`
- **Ingestion failures**: `IngestionJobManager` catches all exceptions, marks job + document as `FAILED`, stores the error message, and leaves no orphaned data.
- **Stream errors**: Yielded as `{"type": "error", "message": "..."}` — the TCP connection closes cleanly; no `ERR_INCOMPLETE_CHUNKED_ENCODING`.
- **RAGAS errors**: Returns a zero `MetricSet` — evaluation run never crashes the API.

---

## 🎯 Design Decisions

1. **Hierarchical parent-child chunking** — Child chunks (500 tokens) are embedded and retrieved for precision; parent chunks (2000 tokens) supply surrounding context to the LLM after retrieval. This avoids the classic RAG trade-off between chunk size for accurate retrieval vs. enough context for a coherent answer.

2. **Hybrid retrieval (dense + BM25) over dense-only** — Policy documents contain exact terms, section numbers, and named roles (e.g. "Individual A", specific dollar thresholds) that semantic embeddings sometimes miss. BM25 keyword matching catches exact-term queries; Qdrant dense search catches paraphrased/semantic queries. Reciprocal Rank Fusion (60/40 weighting) combines both rather than picking one.

3. **Cross-encoder reranking (Cohere) as a second pass** — Embedding similarity alone is a weak relevance signal once the candidate pool grows. A cross-encoder reranker scores each candidate chunk against the actual query text, producing a materially more relevant top-N before it reaches the LLM — improving answer quality without changing chunk size or embedding model.

4. **Shared document corpus, not per-user namespaces** — This is a *company* knowledge assistant: all employees should see the same uploaded policies. Documents are tagged into a single `"shared"` namespace rather than siloed per-uploader; RBAC (admin vs. user) controls who can *modify* the corpus, not who can *see* it.

5. **Query rewriting before retrieval** — Multi-turn conversations need pronoun/reference resolution ("what about that policy?" → "what is the procurement policy threshold?") before they can be used as a search query. An LLM rewriter step turns the raw turn into a standalone question, or signals `[NO_RETRIEVAL]` for chitchat/meta-questions so the system doesn't waste a vector search on "thanks!".

6. **Async background ingestion, not synchronous upload** — PDF parsing, chunking, embedding, and indexing can take seconds to minutes for large documents. The upload endpoint returns `202 Accepted` immediately with a `job_id`; ingestion runs as a FastAPI background task, and the frontend polls job progress instead of blocking the HTTP request.

7. **SQLModel over plain SQLAlchemy** — A single class definition serves as both the Pydantic schema (API validation) and the SQLAlchemy ORM model (DB layer), reducing duplication between request/response schemas and table definitions.

8. **JWT (stateless) over server-side sessions** — No session store is needed; any backend replica can validate a token independently, which matters once the API scales beyond one instance.

9. **Provider-per-task instead of one LLM for everything** — Groq handles generation/rewriting/summarisation, OpenRouter handles embeddings, Cohere handles reranking. Each was picked for its free/cheap tier and strength at that specific sub-task, keeping inference cost near-zero during development and evaluation.

---

## 📈 Scalability Considerations

1. **Fully async I/O path** — FastAPI + `asyncpg` + async Qdrant/HTTP clients mean the API can hold many concurrent in-flight requests per worker without thread-per-request overhead.

2. **Stateless API layer** — JWT auth and no in-memory session state mean the backend can be horizontally scaled behind a load balancer with no sticky-session requirement.

3. **External, independently scalable dependencies** — PostgreSQL, Qdrant (Cloud), Groq, OpenRouter, and Cohere all run outside the API process, so the app server stays lightweight and can be scaled independently of the data/inference layer.

4. **Embedding batching with bounded concurrency** — `EmbeddingEngine` batches chunks (size 100) and caps concurrent API calls via a semaphore (5), balancing ingestion throughput against third-party rate limits.

5. **History compression bounds LLM context cost** — Conversations longer than ~3000 tokens are automatically summarised, so LLM cost and latency per turn stay roughly constant regardless of how long a conversation gets.

6. **Known scaling constraint — BM25 index is local disk, not shared.** `BM25Indexer` persists each namespace's keyword index as a `.pkl` file under `BM25_INDEX_DIR` on the container's local filesystem. This works for a single backend replica (or replicas sharing a mounted volume, as in the current Docker Compose setup), but running multiple independently-scaled backend instances without a shared volume would cause BM25 results to diverge between instances. A production scale-out would move this to a shared store (e.g. Redis, S3-backed index, or a dedicated search service like Elasticsearch/OpenSearch).

7. **Ingestion runs as a per-process background task, not a queue.** `BackgroundTasks` runs ingestion in the same process as the API request. This is fine at current scale but doesn't survive a process restart mid-job and doesn't distribute load across workers. A heavier-traffic deployment would move ingestion to a dedicated worker pool (e.g. Celery/RQ workers consuming from Redis or SQS) so the API process never does CPU/IO-heavy parsing.

8. **Upload limits are a cost/abuse guard, not a scaling mechanism.** `MAX_UPLOADS_PER_DAY` and the 50 MB / 500-page caps protect against runaway ingestion cost, but per-user/IP rate limiting on the query endpoints isn't implemented yet — worth adding before opening this up beyond a trusted internal user base.
