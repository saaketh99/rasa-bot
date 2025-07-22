@echo off
echo Starting Rasa Chatbot Application...
echo.

echo Starting Mock Rasa Server...
start "Mock Rasa Server" cmd /k "python mock_rasa_server.py"

echo Starting Rasa Actions Server (Optional)...
start "Rasa Actions" cmd /k "echo Rasa Actions server not needed with mock server"

echo Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "uvicorn app.main:app --reload --port 8000"

echo Starting Frontend...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo All services are starting...
echo.
echo Frontend: http://localhost:3000
echo Rasa API: http://localhost:5005
echo FastAPI: http://localhost:8000
echo.
echo Press any key to exit...
pause > nul 