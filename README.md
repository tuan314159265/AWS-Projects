# News RAG Pipeline on AWS

> End-to-end Data Pipeline: automatically crawl news, process streaming data, normalize the data warehouse, and query with RAG (Retrieval-Augmented Generation) on AWS Fargate.

## Architecture

```text
+----------------+      +----------------+      +----------------+
| News Sources   |----->| Crawl Layer    |----->| Process Layer  |
| (Vietnamese    |      | (Scrapy/Kafka) |      | (ETL/Warehouse)|
|  News Sites)   |      +----------------+      +-------+--------+
+----------------+                                    |
                                                    v
+----------------+      +----------------+      +----------------+
| AI Chat CLI    |<-----| RAG Engine     |<-----| Vector Store   |
| (Retriev+Gen)  |      | (Groq/Gemini)  |      | (Qdrant)       |
+----------------+      +----------------+      +----------------+
```

## Components

| Module | Description |
|--------|-------------|
| `crawler/` | Scrapy spider crawling Vietnamese news sites |
| `consumer/` | Kafka consumer -> PostgreSQL raw storage |
| `etl/` | Transform raw data -> Star Schema Warehouse |
| `vectorize/` | Embed chunks with BGE-small -> Qdrant |
| `search/` | RAG engine: Retriever + Generator with fallback |
| `main.py` | Pipeline orchestrator (crawl -> ETL -> vectorize) |

## Lighter Models Used

| Component | Model | Size |
|-----------|-------|------|
| Embedding | `BAAI/bge-small-en-v1.5` | 33M params |
| LLM (Primary) | `qwen/qwen3-8b-instant` (Groq) | 8B params |
| LLM (Fallback 1) | `meta-llama/llama-3.1-8b-instant` (Groq) | 8B params |
| LLM (Fallback 2) | `gemini-2.0-flash` (Google) | - |

## Quick Start

```bash
# 1. Setup environment
make setup

# 2. Start local services (Kafka, Postgres)
make up

# 3. Run full pipeline (crawl -> ETL -> vectorize)
make full

# 4. Test the RAG engine
make test-interactive
```

## AWS Deployment

```bash
# Requires: aws configure, terraform, docker
chmod +x deploy.sh
./deploy.sh
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Key variables:
- `QDRANT_HOST` / `QDRANT_API_KEY` - Qdrant Cloud connection
- `DB_HOST` / `DB_USER` / `DB_PASSWORD` - PostgreSQL (AWS RDS)
- `MODEL_*_API_KEY` - Groq/Google API keys for LLM
