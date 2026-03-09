# RAG Chatbot - Complete Setup Guide

This guide will walk you through setting up and running the RAG Chatbot application with Gemini AI, PostgreSQL, and pgvector.

## Prerequisites

- **Docker Desktop** installed and running
- **Python 3.12+** installed
- **Node.js 18+** and npm installed
- **Gemini API Key** from Google AI Studio (https://aistudio.google.com/app/apikey)

---

## 🚀 Quick Start (Recommended)

### Step 1: Clone and Navigate

```bash
cd c:\work\KSU\AAI\RAG
```

### Step 2: Set Up Environment Variables

The `.env` file already exists with your API key. Verify it contains:

```bash
GEMINI_API_KEY=your-actual-api-key
DATABASE_URL=postgresql+psycopg2://app:app@localhost:5432/ragdb
EMBED_MODEL=gemini-embedding-001
CHAT_MODEL=gemini-2.5-flash
EMBED_DIM=768
TOP_K=5
```

### Step 3: Start Database

```bash
cd infra
docker compose up -d
cd ..
```

This will:
- Start PostgreSQL 16 with pgvector extension
- Create the `ragdb` database
- Initialize tables (doc_chunks, customers, products, orders, order_items)
- Seed sample sales data

**Verify database is running:**
```bash
docker ps
# Should show: rag-postgres container running on port 5432
```

### Step 4: Install Python Dependencies

```bash
pip install --user -r requirements.txt
```

### Step 5: Start Backend API

```bash
python -m backend.main
```

The API will start at **http://localhost:8000**

**Test the API:**
- Open browser: http://localhost:8000/health
- Should return: `{"status": "healthy", "database": "connected"}`

### Step 6: Install Frontend Dependencies

Open a **new terminal** window:

```bash
cd c:\work\KSU\AAI\RAG\frontend
cmd /c npm install
```

### Step 7: Start Frontend

```bash
cmd /c npm run dev
```

The UI will start at **http://localhost:5173**

### Step 8: Access the Application

Open your browser and go to: **http://localhost:5173**

---

## 🎯 Using the Application

### 1. Ingest Documents (RAG Mode)

Before asking questions, you need to upload documents:

1. Click **"Upload Document"** in the sidebar
2. Paste text content or upload a `.txt` file
3. Click **"Ingest"**
4. Wait for confirmation

### 2. Ask Questions

**RAG Mode** (Document Q&A):
```
What is the main topic of the document?
Summarize the key points.
```

**SQL Mode** (Database Queries):
```
ยอดขายทั้งหมดเท่าไร
แสดงลูกค้า 5 อันดับแรก
สินค้าไหนขายดีที่สุด
```

**Auto Mode** (Intelligent Routing):
- Automatically chooses between RAG and SQL
- Evaluates answer quality
- Rewrites queries if needed (max 2 iterations)

### 3. View Citations

Every answer includes:
- **RAG Mode**: Source document chunks with similarity scores
- **SQL Mode**: Generated SQL query and results
- **Auto Mode**: Routing decision + sources

---

## 🐳 Alternative: Docker Compose Deployment

For production-like deployment with both backend and database in containers:

### Step 1: Set Environment Variable

**Windows PowerShell:**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

**Windows CMD:**
```cmd
set GEMINI_API_KEY=your-api-key-here
```

### Step 2: Start All Services

```bash
docker-compose -f docker-compose.prod.yml up -d
```

This will:
- Start PostgreSQL with pgvector
- Build and start the backend API
- Initialize database with schema and seed data

### Step 3: Check Status

```bash
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs backend
```

### Step 4: Access API

Backend API: **http://localhost:8000**

### Step 5: Run Frontend Separately

```bash
cd frontend
cmd /c npm install
cmd /c npm run dev
```

Frontend UI: **http://localhost:5173**

---

## 📊 Database Information

### Connection Details

- **Host**: localhost
- **Port**: 5432
- **Database**: ragdb
- **User**: app
- **Password**: app

### Tables

1. **doc_chunks** - Vector embeddings for RAG (768 dimensions)
2. **customers** - Sample customer data (10 records)
3. **products** - Sample product data (10 records)
4. **orders** - Sample orders (15 records)
5. **order_items** - Order line items (23 records)

### Access Database Directly

```bash
docker exec -it rag-postgres psql -U app -d ragdb
```

**Example queries:**
```sql
-- List all tables
\dt

-- View customers
SELECT * FROM customers LIMIT 5;

-- View document chunks
SELECT doc_id, chunk_index, LEFT(content, 50) FROM doc_chunks;

-- Check vector index
\d+ doc_chunks
```

---

## 🔧 Troubleshooting

### Backend Won't Start

**Error: `ModuleNotFoundError: No module named 'dotenv'`**

Solution:
```bash
pip install --user python-dotenv
# Or reinstall all dependencies
pip install --user -r requirements.txt
```

**Error: Database connection failed**

Solution:
```bash
# Check if PostgreSQL is running
docker ps | findstr rag-postgres

# Restart database
cd infra
docker compose restart
```

### Frontend Won't Start

**Error: `npm: cannot be loaded because running scripts is disabled`**

Solution:
```bash
# Use cmd /c prefix
cmd /c npm install
cmd /c npm run dev
```

### Database Issues

**Tables not created:**

```bash
# Recreate database
docker exec rag-postgres psql -U app -d postgres -c "DROP DATABASE IF EXISTS ragdb;"
docker exec rag-postgres psql -U app -d postgres -c "CREATE DATABASE ragdb OWNER app;"

# Run initialization
docker cp infra\init_pgvector.sql rag-postgres:/tmp/init.sql
docker exec rag-postgres psql -U app -d ragdb -f /tmp/init.sql

# Seed data
docker cp backend\sql\seed.sql rag-postgres:/tmp/seed.sql
docker exec rag-postgres psql -U app -d ragdb -f /tmp/seed.sql
```

### API Key Issues

**Error: Invalid API key**

1. Get a new key from: https://aistudio.google.com/app/apikey
2. Update `.env` file:
   ```
   GEMINI_API_KEY=your-new-key-here
   ```
3. Restart backend

---

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/chat` | Non-streaming chat |
| POST | `/chat/stream` | Streaming chat (SSE) |
| POST | `/ingest` | Ingest text content |
| POST | `/ingest/file` | Ingest file upload |
| GET | `/documents` | List documents |
| DELETE | `/documents/{doc_id}` | Delete document |

### Example API Calls

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Chat (Non-streaming):**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "ยอดขายทั้งหมดเท่าไร",
    "session_id": "test-session",
    "mode": "sql",
    "top_k": 5
  }'
```

**Ingest Document:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "test-doc",
    "content": "This is a test document about AI and machine learning."
  }'
```

---

## 🛑 Stopping the Application

### Stop Backend
Press `Ctrl+C` in the backend terminal

### Stop Frontend
Press `Ctrl+C` in the frontend terminal

### Stop Database
```bash
cd infra
docker compose down
```

### Stop Docker Compose Deployment
```bash
docker-compose -f docker-compose.prod.yml down
```

### Stop and Remove All Data
```bash
docker-compose -f docker-compose.prod.yml down -v
```

---

## 🎓 Next Steps

1. **Upload your own documents** - Use the document upload feature
2. **Try different modes** - Compare RAG, SQL, and Auto modes
3. **Explore the code** - Check `backend/` and `frontend/src/`
4. **Customize prompts** - Edit `backend/rag/prompts.py`
5. **Add more data** - Insert into PostgreSQL tables for SQL RAG

---

## 📚 Additional Resources

- **Gemini API Docs**: https://ai.google.dev/docs
- **pgvector**: https://github.com/pgvector/pgvector
- **FastAPI**: https://fastapi.tiangolo.com/
- **React**: https://react.dev/

---

## ⚙️ Configuration

All settings are in `.env`:

```bash
GEMINI_API_KEY=       # Your Gemini API key
DATABASE_URL=         # PostgreSQL connection string
EMBED_MODEL=          # gemini-embedding-001 (768-dim)
CHAT_MODEL=           # gemini-2.5-flash
EMBED_DIM=            # 768 (for HNSW index compatibility)
TOP_K=                # Number of chunks to retrieve (default: 5)
```

**Note**: Embedding dimension is set to 768 (not 3072) to support HNSW indexing in pgvector, which has a 2000-dimension limit.
