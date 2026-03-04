#!/bin/bash

# Resident Directory Backend Startup Script

echo "Starting Resident Directory Backend API..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate 2>/dev/null || . venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Generate OpenAPI spec
echo "Generating OpenAPI specification..."
python -m src.api.generate_openapi

# Start the server
echo "Starting FastAPI server on port 3001..."
uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload
