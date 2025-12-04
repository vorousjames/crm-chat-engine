#!/bin/bash

# Simple Local Indexing Script
# Run this when you want to update embeddings in production

set -e

echo "🔄 Running local indexing to Weaviate Cloud..."

# Check if .env.production exists
if [[ ! -f ".env.production" ]]; then
    echo "❌ Missing .env.production file"
    echo "Copy .env.production.example and update with your values"
    exit 1
fi

# Load production environment
export $(grep -v '^#' .env.production | xargs)

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
if [[ -d "venv" ]]; then
    echo "🔧 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found. Using system Python..."
fi

# Run indexing
python handler.py

echo "✅ Indexing complete!"