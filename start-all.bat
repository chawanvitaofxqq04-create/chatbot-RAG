@echo off
echo ========================================
echo RAG Chatbot - Start Database + Backend
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Copying .env.example to .env...
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit .env and set your GEMINI_API_KEY
    echo Then run this script again.
    pause
    exit /b 1
)

echo Step 1: Starting PostgreSQL + pgvector...
cd infra
docker compose up -d
cd ..
echo Waiting for database to be ready...
timeout /t 10 /nobreak >nul

echo.
echo Step 2: Building backend Docker image...
docker build -t rag-backend .
if %errorlevel% neq 0 (
    echo ERROR: Docker build failed!
    pause
    exit /b 1
)

echo.
echo Step 3: Stopping old backend container (if exists)...
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
    echo ERROR: Failed to start backend!
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS! All services are running
echo ========================================
echo.
echo Database: rag-postgres (port 5432)
echo Backend:  rag-backend-app (port 8000)
echo.
echo API Health Check: http://localhost:8000/health
echo.
echo View logs:
echo   docker logs -f rag-backend-app
echo.
echo Stop all:
echo   docker stop rag-backend-app rag-postgres
echo.
echo Next step: Start the frontend
echo   cd frontend
echo   npm install
echo   npm run dev
echo.
pause
