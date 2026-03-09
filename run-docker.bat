@echo off
echo ========================================
echo RAG Chatbot - Docker Deployment
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and set your GEMINI_API_KEY
    pause
    exit /b 1
)

echo Step 1: Building Docker image...
docker build -t rag-backend .
if %errorlevel% neq 0 (
    echo ERROR: Docker build failed!
    pause
    exit /b 1
)

echo.
echo Step 2: Checking if rag-postgres is running...
docker ps | findstr rag-postgres >nul
if %errorlevel% neq 0 (
    echo Starting PostgreSQL container...
    cd infra
    docker compose up -d
    cd ..
    timeout /t 5 /nobreak >nul
) else (
    echo PostgreSQL is already running.
)

echo.
echo Step 3: Stopping existing backend container (if any)...
docker stop rag-backend-app 2>nul
docker rm rag-backend-app 2>nul

echo.
echo Step 4: Starting backend container...
docker run -d ^
  --name rag-backend-app ^
  --network infra_default ^
  -p 8000:8000 ^
  --env-file .env ^
  -e DATABASE_URL=postgresql+psycopg2://app:app@rag-postgres:5432/ragdb ^
  rag-backend

if %errorlevel% neq 0 (
    echo ERROR: Failed to start backend container!
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS! Backend is running in Docker
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo Health Check: http://localhost:8000/health
echo.
echo To view logs:
echo   docker logs -f rag-backend-app
echo.
echo To stop:
echo   docker stop rag-backend-app
echo.
pause
