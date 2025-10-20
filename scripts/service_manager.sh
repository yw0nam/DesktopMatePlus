#!/bin/bash
# Quick start script for DesktopMate+ development environment
# This script helps you start all required services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 DesktopMate+ Service Manager"
echo "================================"
echo ""

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
echo "📋 Checking dependencies..."

if ! command_exists python; then
    echo -e "${RED}❌ Python is not installed${NC}"
    exit 1
fi

if ! command_exists uv; then
    echo -e "${YELLOW}⚠️  uv is not installed. Install it with: pip install uv${NC}"
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"
echo ""

# Show current service status
echo "📊 Current Service Status:"
echo "-------------------------"

if check_port 8000; then
    echo -e "  FastAPI Backend (8000): ${GREEN}RUNNING${NC}"
else
    echo -e "  FastAPI Backend (8000): ${YELLOW}STOPPED${NC}"
fi

if check_port 8001; then
    echo -e "  VLM Service (8001):     ${GREEN}RUNNING${NC}"
else
    echo -e "  VLM Service (8001):     ${YELLOW}STOPPED${NC}"
fi

if check_port 8080; then
    echo -e "  TTS Service (8080):     ${GREEN}RUNNING${NC}"
else
    echo -e "  TTS Service (8080):     ${YELLOW}STOPPED${NC}"
fi

echo ""
echo "What would you like to do?"
echo "1) Start FastAPI Backend only (requires VLM and TTS already running)"
echo "2) Stop all services"
echo "3) Check service health"
echo "4) View logs"
echo "5) Show configuration"
echo "6) Exit"
echo ""
read -p "Enter your choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo "🌐 Starting FastAPI Backend..."

        # Check if external services are running
        if ! check_port 8001; then
            echo -e "${YELLOW}⚠️  VLM service (port 8001) is not running${NC}"
            echo "   The backend will start but VLM features won't work"
            echo "   To start VLM: python -m vllm.entrypoints.openai.api_server --model YOUR_MODEL --port 8001"
        fi

        if ! check_port 8080; then
            echo -e "${YELLOW}⚠️  TTS service (port 8080) is not running${NC}"
            echo "   The backend will start but TTS features won't work"
            echo "   To start TTS: python -m fish_speech.api.start_http_api --listen 127.0.0.1:8080"
        fi

        echo ""
        echo "Starting backend..."

        # Load environment variables if .env exists
        if [ -f .env ]; then
            export $(cat .env | grep -v '^#' | xargs)
        fi

        # Start the backend
        if command_exists uv; then
            uv run python -m src.main
        else
            python -m src.main
        fi
        ;;

    2)
        echo ""
        echo "🛑 Stopping all services..."

        # Stop FastAPI Backend
        if check_port 8000; then
            echo "  Stopping FastAPI Backend (8000)..."
            kill $(lsof -ti:8000) 2>/dev/null || true
            echo -e "  ${GREEN}✅ Stopped${NC}"
        fi

        # Stop VLM Service
        if check_port 8001; then
            echo "  Stopping VLM Service (8001)..."
            kill $(lsof -ti:8001) 2>/dev/null || true
            echo -e "  ${GREEN}✅ Stopped${NC}"
        fi

        # Stop TTS Service
        if check_port 8080; then
            echo "  Stopping TTS Service (8080)..."
            kill $(lsof -ti:8080) 2>/dev/null || true
            echo -e "  ${GREEN}✅ Stopped${NC}"
        fi

        echo ""
        echo -e "${GREEN}✅ All services stopped${NC}"
        ;;

    3)
        echo ""
        echo "🏥 Checking service health..."
        echo ""

        if check_port 8000; then
            echo "Testing FastAPI Backend..."
            curl -s http://localhost:8000/health | python -m json.tool || echo -e "${RED}Failed to connect${NC}"
        else
            echo -e "${RED}FastAPI Backend is not running${NC}"
        fi

        echo ""

        if check_port 8001; then
            echo "Testing VLM Service..."
            curl -s http://localhost:8001/v1/models || echo -e "${RED}Failed to connect${NC}"
        else
            echo -e "${RED}VLM Service is not running${NC}"
        fi

        echo ""
        ;;

    4)
        echo ""
        echo "📜 Recent logs:"
        echo "================================"

        if [ -f logs/backend.log ]; then
            echo "Backend logs (last 20 lines):"
            tail -n 20 logs/backend.log
        else
            echo "No backend logs found"
        fi
        ;;

    5)
        echo ""
        echo "⚙️  Current Configuration:"
        echo "================================"

        if [ -f .env ]; then
            echo "From .env file:"
            cat .env | grep -v '^#' | grep -v '^$'
        else
            echo "No .env file found"
            echo ""
            echo "Using default configuration:"
            echo "  FASTAPI_HOST=127.0.0.1"
            echo "  FASTAPI_PORT=8000"
            echo "  FASTAPI_VLM_BASE_URL=http://localhost:8001"
            echo "  FASTAPI_TTS_BASE_URL=http://localhost:8080"
        fi

        echo ""
        ;;

    6)
        echo "👋 Goodbye!"
        exit 0
        ;;

    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
