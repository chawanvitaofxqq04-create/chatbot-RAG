Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RAG Chatbot - Docker Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.example to .env and set your GEMINI_API_KEY" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Step 1: Building Docker image..." -ForegroundColor Green
docker build -t rag-backend .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Step 2: Checking if rag-postgres is running..." -ForegroundColor Green
$postgresRunning = docker ps --format "{{.Names}}" | Select-String -Pattern "rag-postgres"
if (-not $postgresRunning) {
    Write-Host "Starting PostgreSQL container..." -ForegroundColor Yellow
    Set-Location infra
    docker compose up -d
    Set-Location ..
    Start-Sleep -Seconds 5
} else {
    Write-Host "PostgreSQL is already running." -ForegroundColor Green
}

Write-Host ""
Write-Host "Step 3: Stopping existing backend container (if any)..." -ForegroundColor Green
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
    Write-Host "ERROR: Failed to start backend container!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS! Backend is running in Docker" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Health Check: http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  docker logs -f rag-backend-app" -ForegroundColor White
Write-Host ""
Write-Host "To stop:" -ForegroundColor Yellow
Write-Host "  docker stop rag-backend-app" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"
