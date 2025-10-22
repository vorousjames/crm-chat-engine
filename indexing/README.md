# Simple Local Indexing

## What This Does

Run indexing locally, upload embeddings to Weaviate Cloud. No deployed indexing services needed.

## Setup (One Time)

### 1. Get Weaviate Cloud

1. Go to [Weaviate Cloud Console](https://console.weaviate.io)
2. Create a cluster
3. Get your URL and API key

### 2. Configure

```bash
cp .env.production.example .env.production
```

Edit `.env.production`:

```bash
WEAVIATE_URL=https://your-cluster.weaviate.cloud
WEAVIATE_API_KEY=your-api-key
CODEBASE_PATH=/path/to/your/app/to/index
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Usage

When you want to update embeddings:

```bash
./index-locally.sh
```

That's it! Your production chat server will automatically use the new embeddings.

## Production Chat Server Setup

Point your Heroku chat server to the cloud Weaviate:

```bash
heroku config:set WEAVIATE_URL=https://your-cluster.weaviate.cloud
heroku config:set WEAVIATE_API_KEY=your-api-key
```

## Architecture

```
Your Local Machine (indexing) → Weaviate Cloud → Heroku Chat Server → RunPod Inference
```

Simple. Clean. No indexing infrastructure to maintain.
