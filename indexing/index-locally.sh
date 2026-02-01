#!/bin/bash

# Simple Local Indexing Script
# Run this when you want to update embeddings in production

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 Running local indexing to Weaviate Cloud..."

# Check if .env.production exists in the script's directory
ENV_FILE="${SCRIPT_DIR}/.env.production"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ Missing .env.production file"
    echo "Expected location: $ENV_FILE"
    echo "Copy .env.production.example and update with your values"
    exit 1
fi

# Load production environment
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Check required variables
if [[ -z "$WEAVIATE_URL" ]] || [[ -z "$WEAVIATE_API_KEY" ]] || [[ -z "$CODEBASE_PATH" ]]; then
    echo "❌ Missing required variables in .env.production"
    echo "Need: WEAVIATE_URL, WEAVIATE_API_KEY, CODEBASE_PATH"
    exit 1
fi

echo "📂 Codebase: $CODEBASE_PATH"
echo "🌐 Weaviate: $WEAVIATE_URL"
echo ""

# Activate virtual environment
if [[ -d "${SCRIPT_DIR}/venv" ]]; then
    echo "🔧 Activating virtual environment..."
    source "${SCRIPT_DIR}/venv/bin/activate"
else
    echo "⚠️  No virtual environment found. Using system Python..."
fi

# Change to script directory to run handler.py
cd "$SCRIPT_DIR"

# Run indexing
python handler.py

echo "✅ Indexing complete!"