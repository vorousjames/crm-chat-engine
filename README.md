# CRM Chat Engine

An AI-powered chatbot system for home-service CRM applications, providing intelligent responses based on indexed codebase knowledge.

## Architecture Overview

```
Your SaaS Codebase → Local Indexing Service → Weaviate Cloud → Chat Server (Heroku) → AI Inference (RunPod)
```

**Key Point**: This chat engine project is separate from your SaaS codebase. The indexing service runs locally and points to your external SaaS project via the `CODEBASE_PATH` environment variable, then uploads the processed embeddings to Weaviate Cloud for the chat server to query.

## Components

### 📡 **Chat Server** (`chat-server/`)

Express.js API server that handles chat requests and provides the main interface for the chatbot.

- **Technology**: Node.js, Express.js, Weaviate client
- **Purpose**: Receives chat messages, queries vector database, and coordinates with AI inference
- **Key Features**:
  - API key authentication
  - Rate limiting and security middleware
  - Conversation management
  - Real-time chat endpoints
- **Deployment**: Heroku (configured via `Procfile`)

### 🔍 **Indexing Service** (`indexing/`)

Python-based service that processes and indexes **your separate SaaS codebase** into vector embeddings.

- **Technology**: Python, SentenceTransformers, Weaviate
- **Purpose**: Analyzes your external SaaS application code and creates searchable embeddings for semantic retrieval
- **Key Architecture**:
  - **Runs locally** on your machine where your SaaS codebase exists
  - **Points to external codebase** via `CODEBASE_PATH` environment variable
  - **Uploads embeddings** to Weaviate Cloud for chat server to query
- **Key Features**:
  - Cross-project indexing (indexes external codebases)
  - Automatic code parsing and chunking
  - Vector embedding generation
  - Weaviate Cloud integration
- **Configuration**: Set `CODEBASE_PATH=/path/to/your/saas/project` in `.env.production`
- **Usage**: Run `./index-locally.sh` to update embeddings (NOTE: this is intended to only be done locally)

### 🤖 **Inference Server** (`inference-server/`)

Containerized AI model server for generating intelligent responses.

- **Technology**: Python, PyTorch, Transformers, RunPod
- **Purpose**: Hosts the AI model (DeepSeek Coder) for code-aware chat responses
- **Key Features**:
  - GPU-accelerated inference
  - Serverless scaling
  - Docker containerization
  - Multiple model support options
- **Deployment**: RunPod serverless platform

### 🗄️ **Vector Database**

Weaviate instance for storing and querying code embeddings.

- **Local Development**: Docker Compose setup
- **Production**: Weaviate Cloud
- **Purpose**: Fast semantic search across indexed codebase

## Quick Start

### Development Setup

1. **Start local vector database:**

   ```bash
   docker-compose up -d
   ```

2. **Run the chat server:**

   ```bash
   cd chat-server
   npm install
   npm run dev
   ```

3. **Index your external SaaS codebase:**
   ```bash
   cd indexing
   pip install -r requirements.txt
   # Configure .env.production with path to your SaaS codebase:
   # CODEBASE_PATH=/path/to/your/saas/project
   ./index-locally.sh
   ```

### Production Deployment

1. **Deploy chat server to Heroku** (automatic via `Procfile`)
2. **Set up Weaviate Cloud** and configure environment variables
3. **Deploy inference server to RunPod** using provided Docker configuration
4. **Run indexing locally** to populate vector database

## Environment Variables

- `WEAVIATE_URL` - Weaviate instance URL
- `WEAVIATE_API_KEY` - Weaviate authentication key
- `RUNPOD_ENDPOINT_URL` - RunPod inference endpoint
- `API_KEY` - Chat server authentication key
- `CODEBASE_PATH` - **Path to your external SaaS codebase** (for indexing service)

## Cross-Project Setup

This chat engine is designed to work with your separate SaaS application:

1. **Keep projects separate**: Your SaaS app and this chat engine are independent
2. **Configure indexing**: Point the indexing service to your SaaS codebase:
   ```bash
   # In indexing/.env.production
   CODEBASE_PATH=/Users/yourname/path/to/your-saas-project
   ```
3. **Index periodically**: Run indexing whenever your SaaS codebase changes
4. **Query anywhere**: The chat server can be deployed independently and will have knowledge of your SaaS codebase## Usage

Send POST requests to the chat server:

```bash
curl -X POST http://localhost:3001/api/chat/ask \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "message": "How do I implement user authentication?",
    "conversationId": "unique-conversation-id"
  }'
```

## Key Features

- 🧠 **Contextual AI responses** based on your actual codebase
- 🔒 **Secure API** with key-based authentication
- ⚡ **Scalable architecture** with serverless inference
- 🏗️ **Easy deployment** to cloud platforms
- 🔄 **Real-time indexing** for up-to-date knowledge
