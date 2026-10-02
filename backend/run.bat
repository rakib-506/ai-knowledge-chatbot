@echo off
REM Start the backend on Windows (run from the backend folder, with venv active)
uvicorn app.main:app --reload --port 8000
