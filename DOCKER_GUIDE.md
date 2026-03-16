# Running RAG Chatbot with Docker

This guide shows you how to run the Python backend as a Docker container.

## 🐳 Quick Start

### Option 1: Using the Automated Script (Easiest)

**Windows Command Prompt:**
```cmd
run-docker.bat
```

**Windows PowerShell:**
```powershell
.\run-docker.ps1
```

This script will:
1. Build the Docker image
2. Start PostgreSQL (if not running)
3. Start the backend container
4. Configure networking automatically

### Option 2: Manual Docker Commands

#### Step 1: Build the Docker Image

```bash
docker build -t rag-backend .
```

#### Step 2: Ensure PostgreSQL is Running

```bash
cd infra
docker compose up -d
cd ..
```

#### Step 3: Run the Backend Container

```bash
docker run -d \
  --name rag-backend-app \
  --network infra_default \
  -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql+psycopg2://app:app@rag-postgres:5432/ragdb \
  rag-backend
```

**Note:** The `--network infra_default` connects the backend to the same network as PostgreSQL.

### Option 3: Docker Compose (All Services)

Use the production compose file to run everything together:

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

This starts both PostgreSQL and the backend in one command.

---

## 📊 Verify It's Running

### Check Container Status

```bash
docker ps
```

You should see:
- `rag-postgres` (PostgreSQL)
- `rag-backend-app` (Backend API)

### Test the API

Open browser: **http://localhost:8000/health**

Or use curl:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### View Logs

```bash
# Follow logs in real-time
docker logs -f rag-backend-app

# View last 100 lines
docker logs --tail 100 rag-backend-app
```

---

## 🔧 Managing the Container

### Stop the Backend

```bash
docker stop rag-backend-app
```

### Start the Backend Again

```bash
docker start rag-backend-app
```

### Restart the Backend

```bash
docker restart rag-backend-app
```

### Remove the Container

```bash
docker stop rag-backend-app
docker rm rag-backend-app
```

### Rebuild After Code Changes

```bash
# Stop and remove old container
docker stop rag-backend-app
docker rm rag-backend-app

# Rebuild image
docker build -t rag-backend .

# Run new container
docker run -d \
  --name rag-backend-app \
  --network infra_default \
  -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql+psycopg2://app:app@rag-postgres:5432/ragdb \
  rag-backend
```

Or use the script:
```bash
run-docker.bat
```

---

## 🌐 Frontend Setup

The frontend still runs locally (not in Docker):

```bash
cd frontend
cmd /c npm install
cmd /c npm run dev
```

Access at: **http://localhost:5173**

---

## 🐛 Troubleshooting

### Container Exits Immediately

Check logs:
```bash
docker logs rag-backend-app
```

Common issues:
- Missing `.env` file
- Invalid GEMINI_API_KEY
- Database not accessible

### Cannot Connect to Database

Make sure both containers are on the same network:
```bash
# Check networks
docker network ls

# Inspect the network
docker network inspect infra_default
```

Both `rag-postgres` and `rag-backend-app` should be listed.

### Port Already in Use

If port 8000 is already in use:
```bash
# Use a different port
docker run -d \
  --name rag-backend-app \
  --network infra_default \
  -p 8080:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql+psycopg2://app:app@rag-postgres:5432/ragdb \
  rag-backend
```

Then access at: **http://localhost:8080**

### Environment Variables Not Loading

Verify `.env` file exists and has correct format:
```bash
type .env
```

Should contain:
```
GEMINI_API_KEY=your-actual-key
DATABASE_URL=postgresql+psycopg2://app:app@localhost:5432/ragdb
EMBED_MODEL=gemini-embedding-001
CHAT_MODEL=gemini-2.5-flash
EMBED_DIM=768
TOP_K=5
```

---

## 📦 Docker Image Details

### Image Information

```bash
# View image
docker images | findstr rag-backend

# Inspect image
docker inspect rag-backend
```

### Image Size

The image is based on `python:3.12-slim` and includes:
- Python 3.12
- All dependencies from `requirements.txt`
- Backend application code

Expected size: ~500-800 MB

### Remove Image

```bash
docker rmi rag-backend
```

---

## 🔄 Complete Cleanup

To remove everything and start fresh:

```bash
# Stop all containers
docker stop rag-backend-app rag-postgres
docker rm rag-backend-app rag-postgres

# Remove image
docker rmi rag-backend

# Remove volumes (WARNING: deletes database data)
docker volume rm infra_pgdata

# Remove network
docker network rm infra_default
```

---

## 📝 Environment Variables in Docker

The backend container uses these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Your Gemini API key |
| `DATABASE_URL` | `postgresql+psycopg2://app:app@rag-postgres:5432/ragdb` | Database connection |
| `EMBED_MODEL` | `gemini-embedding-001` | Embedding model |
| `CHAT_MODEL` | `gemini-2.5-flash` | Chat model |
| `EMBED_DIM` | `768` | Embedding dimensions |
| `TOP_K` | `5` | Number of chunks to retrieve |

**Note:** When running in Docker, the `DATABASE_URL` uses `rag-postgres` as the hostname (container name) instead of `localhost`.

---

## 🚀 Production Deployment

For production, use `docker-compose.prod.yml`:

```bash
# Set environment variable
set GEMINI_API_KEY=your-key-here

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop all services
docker-compose -f docker-compose.prod.yml down
```

This is the recommended approach for production deployments.

