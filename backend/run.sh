#!/bin/sh
# Start the backend on Mac/Linux (run from the backend folder, with venv active)
uvicorn app.main:app --reload --port 8000
