# RAG Chatbot Workshop

Web App Chatbot with **Gemini RAG + SQL RAG + Agentic RAG** using PostgreSQL + pgvector.

## Architecture

```
User (Browser) → React Frontend → FastAPI Backend → Gemini API (embeddings + generation)
                                                   → PostgreSQL + pgvector (vector search)
                                                   → PostgreSQL tables (SQL RAG)
```

## Features

- **RAG Mode** — Document Q&A with vector similarity search (pgvector)
- **SQL Mode** — Natural language to SQL via Gemini function calling (read-only, validated)
- **Auto Mode** — Agentic routing with context evaluation and query rewriting (max 2 iterations)
- **Streaming** — SSE-based streaming responses
- **Citations** — Every answer references source chunks or SQL queries
- **Document Management** — Upload, list, and delete documents via UI

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Set your Gemini API key
export GEMINI_API_KEY=your-api-key-here

# Start all services (PostgreSQL + Backend)
docker-compose -f docker-compose.prod.yml up -d

# API runs at http://localhost:8000
# Frontend needs to be run separately (see below)
```

### Option 2: Local Development

#### 1. Start PostgreSQL + pgvector

```bash
cd infra
docker compose up -d
```

#### 2. Set up environment

```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

#### 3. Install & run backend

```bash
pip install -r requirements.txt
python -m backend.main
# API runs at http://localhost:8000
```

#### 4. Install & run frontend

```bash
cd frontend
npm install
npm run dev
# UI runs at http://localhost:5173
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (DB connectivity) |
| POST | `/chat` | Non-streaming chat (Agentic RAG) |
| POST | `/chat/stream` | Streaming chat via SSE |
| POST | `/ingest` | Ingest text content |
| POST | `/ingest/file` | Ingest a text file |
| GET | `/documents` | List ingested documents |
| DELETE | `/documents/{doc_id}` | Delete a document |

## Chat Request

```json
{
  "message": "ยอดขายเดือนมกราคมเท่าไร",
  "session_id": "demo",
  "mode": "auto",
  "top_k": 5
}
```

- `mode`: `"rag"` | `"sql"` | `"auto"`

## Project Structure

```
backend/
  main.py                 # FastAPI app
  config.py               # Settings (env vars)
  rag/
    prompts.py            # Prompt templates
    ingest.py             # Chunking + embedding + pgvector insert
    retriever_pgvector.py # Cosine similarity retrieval
  sql/
    schema.sql            # DB schema reference
    seed.sql              # Sample sales data
    sql_tool.py           # SQL validation + execution
    function_calling_sql.py # Gemini function calling for text-to-SQL
  agent/
    graph.py              # Agentic RAG orchestrator
frontend/
  src/
    App.tsx               # Chat UI
    api.ts                # API client
infra/
  docker-compose.yml      # PostgreSQL + pgvector
  init_pgvector.sql       # Schema initialization
```

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Database**: PostgreSQL 16 + pgvector
- **LLM**: Google Gemini (gemini-2.5-flash + gemini-embedding-001)
- **SDK**: google-genai
