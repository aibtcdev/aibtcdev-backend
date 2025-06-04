#!/bin/bash

set -e

echo "🚀 Setting up aibtcdev-backend development environment..."

# Initialize git submodules if they exist
if [ -f .gitmodules ]; then
    echo "📦 Updating git submodules..."
    git submodule init
    git submodule update --remote
fi

# Install Python dependencies using uv
echo "🐍 Installing Python dependencies..."
if [ -f "uv.lock" ]; then
    uv sync --frozen
else
    uv pip install -r requirements.txt
fi

# Install TypeScript dependencies with Bun
if [ -d "agent-tools-ts" ]; then
    echo "📋 Installing TypeScript dependencies..."
    cd agent-tools-ts
    if [ -f "bun.lock" ]; then
        bun install --frozen-lockfile
    else
        bun install
    fi
    cd ..
fi

# Set up any additional configuration
echo "⚙️  Setting up environment..."
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please configure your .env file with appropriate values"
fi

echo "✅ Environment setup complete!"
echo "🔧 You can now run the development server with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload" 