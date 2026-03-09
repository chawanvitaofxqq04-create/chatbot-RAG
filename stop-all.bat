@echo off
echo ========================================
echo Stopping RAG Chatbot Services
echo ========================================
echo.

echo Stopping backend container...
docker stop rag-backend-app 2>nul
docker rm rag-backend-app 2>nul

echo Stopping database container...
cd infra
docker compose down
cd ..

echo.
echo ========================================
echo All services stopped
echo ========================================
echo.
pause
