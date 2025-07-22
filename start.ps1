Write-Host "Starting Rasa Chatbot Application..." -ForegroundColor Green
Write-Host ""

# Start Mock Rasa Server
Write-Host "Starting Mock Rasa Server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python mock_rasa_server.py"

# Start Rasa Actions Server (Optional)
Write-Host "Starting Rasa Actions Server (Optional)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "echo Rasa Actions server not needed with mock server"

# Start FastAPI Backend
Write-Host "Starting FastAPI Backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn app.main:app --reload --port 8000"

# Start Frontend
Write-Host "Starting Frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host ""
Write-Host "All services are starting..." -ForegroundColor Green
Write-Host ""
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Rasa API: http://localhost:5005" -ForegroundColor Cyan
Write-Host "FastAPI: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 