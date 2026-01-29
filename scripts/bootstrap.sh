#!/bin/bash
set -e

# Song2Video Bootstrap Script
# One-liner: curl -fsSL https://raw.githubusercontent.com/DanOps-1/awesome-song2video/main/scripts/bootstrap.sh | bash

REPO_URL="https://github.com/DanOps-1/awesome-song2video.git"
PROJECT_DIR="awesome-song2video"

echo "🎬 Song2Video Bootstrap Script"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

# Check command exists
check_cmd() {
    if command -v "$1" &> /dev/null; then
        success "$1 found: $(command -v $1)"
        return 0
    else
        return 1
    fi
}

# Check dependencies
echo "📋 Checking dependencies..."
echo ""

# Python
if check_cmd python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        success "Python version $PYTHON_VERSION (>= 3.11)"
    else
        warn "Python $PYTHON_VERSION found, but 3.11+ recommended"
    fi
else
    error "Python 3.11+ is required. Install from https://python.org"
fi

# Node.js
if check_cmd node; then
    NODE_VERSION=$(node --version | cut -d'v' -f2)
    NODE_MAJOR=$(echo $NODE_VERSION | cut -d'.' -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        success "Node.js version $NODE_VERSION (>= 18)"
    else
        warn "Node.js $NODE_VERSION found, but 18+ recommended"
    fi
else
    error "Node.js 18+ is required. Install from https://nodejs.org"
fi

# FFmpeg
if check_cmd ffmpeg; then
    success "FFmpeg found"
else
    warn "FFmpeg not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if check_cmd brew; then
            brew install ffmpeg
        else
            error "Please install Homebrew first: https://brew.sh"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if check_cmd apt-get; then
            sudo apt-get update && sudo apt-get install -y ffmpeg
        elif check_cmd yum; then
            sudo yum install -y ffmpeg
        else
            error "Please install FFmpeg manually"
        fi
    else
        error "Please install FFmpeg manually: https://ffmpeg.org"
    fi
fi

# Redis
if check_cmd redis-server; then
    success "Redis found"
else
    warn "Redis not found. Will use Docker for Redis."
fi

# uv (Python package manager)
if check_cmd uv; then
    success "uv found"
else
    warn "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    success "uv installed"
fi

echo ""
echo "📥 Cloning repository..."

if [ -d "$PROJECT_DIR" ]; then
    warn "Directory $PROJECT_DIR already exists"
    cd "$PROJECT_DIR"
    git pull origin main
else
    git clone "$REPO_URL"
    cd "$PROJECT_DIR"
fi

success "Repository cloned"

echo ""
echo "📦 Installing dependencies..."

# Python dependencies
uv sync
success "Python dependencies installed"

# Frontend dependencies
cd apps/frontend && npm install --silent
cd ../web && npm install --silent
cd ../..
success "Frontend dependencies installed"

echo ""
echo "⚙️ Setting up environment..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    warn "Created .env file. Please edit it with your API keys:"
    echo "   - TL_API_KEY: TwelveLabs API key"
    echo "   - TL_INDEX_ID: TwelveLabs index ID"
    echo ""
    echo "Get your API key at: https://api.twelvelabs.io"
fi

echo ""
echo "🚀 Starting services..."

# Start with Docker if available, otherwise manual
if check_cmd docker && check_cmd docker-compose; then
    docker compose up -d
    success "Services started with Docker"
else
    bash start.sh &
    success "Services started manually"
fi

echo ""
echo "================================"
echo -e "${GREEN}🎉 Song2Video is ready!${NC}"
echo "================================"
echo ""
echo "📍 Access points:"
echo "   🎨 User Frontend:  http://localhost:6008"
echo "   ⚙️  Admin Dashboard: http://localhost:6006"
echo "   📚 API Docs:       http://localhost:8000/docs"
echo ""
echo "📝 Next steps:"
echo "   1. Edit .env with your TwelveLabs API key"
echo "   2. Open http://localhost:6008 in your browser"
echo "   3. Upload an audio file and start creating!"
echo ""
echo "📖 Documentation: https://github.com/DanOps-1/awesome-song2video/docs"
echo ""

# Open browser (optional)
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 3
    open "http://localhost:6008" 2>/dev/null || true
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sleep 3
    xdg-open "http://localhost:6008" 2>/dev/null || true
fi
