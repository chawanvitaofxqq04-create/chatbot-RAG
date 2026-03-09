Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stopping RAG Chatbot Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Stopping backend container..." -ForegroundColor Yellow
docker stop rag-backend-app 2>$null
docker rm rag-backend-app 2>$null

Write-Host "Stopping database container..." -ForegroundColor Yellow
Set-Location infra
docker compose down
Set-Location ..

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "All services stopped" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
