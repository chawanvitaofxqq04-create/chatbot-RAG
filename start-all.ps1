Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RAG Chatbot - Start Database + Backend" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host ""
    Write-Host "IMPORTANT: Edit .env and set your GEMINI_API_KEY" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Step 1: Starting PostgreSQL + pgvector..." -ForegroundColor Green
Set-Location infra
docker compose up -d
Set-Location ..
Write-Host "Waiting for database to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "Step 2: Building backend Docker image..." -ForegroundColor Green
docker build -t rag-backend .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 3: Stopping old backend container (if exists)..." -ForegroundColor Green
docker stop rag-backend-app 2>$null
docker rm rag-backend-app 2>$null

Write-Host ""
Write-Host "Step 4: Starting backend container..." -ForegroundColor Green
docker run -d `
  --name rag-backend-app `
  --network infra_default `
  -p 8000:8000 `
  --env-file .env `
  -e DATABASE_URL=postgresql+psycopg2://app:app@rag-postgres:5432/ragdb `
  rag-backend

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start backend!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS! All services are running" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Database: rag-postgres (port 5432)" -ForegroundColor Cyan
Write-Host "Backend:  rag-backend-app (port 8000)" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Health Check: http://localhost:8000/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "View logs:" -ForegroundColor White
Write-Host "  docker logs -f rag-backend-app" -ForegroundColor Gray
Write-Host ""
Write-Host "Stop all:" -ForegroundColor White
Write-Host "  docker stop rag-backend-app rag-postgres" -ForegroundColor Gray
Write-Host ""
Write-Host "Next step: Start the frontend" -ForegroundColor Yellow
Write-Host "  cd frontend" -ForegroundColor Gray
Write-Host "  npm install" -ForegroundColor Gray
Write-Host "  npm run dev" -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to exit"
