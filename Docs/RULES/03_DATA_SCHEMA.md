# Data Schema — News RAG Pipeline on AWS

## Mục tiêu
Chuẩn hóa cấu trúc dữ liệu qua các module: Kafka message format, Star Schema PostgreSQL, Qdrant vector payload, Pydantic models, và biến môi trường.

---

## 1. Crawler Output (Data File)

Module: `crawler/spiders/spider.py` → `data/articles.json`

### Crawler → JSON File (`data/articles.json`)

```json
{
  "title": "Tiêu đề bài báo",
  "content": "Nội dung bài báo (HTML + text)",
  "url": "https://vnexpress.net/bai-bao-123.html",
  "source": "vnexpress",
  "author": "Tên tác giả",
  "publish_date": "2026-07-20T10:30:00+07:00"
}
```

| Field | Type | Nguồn | Ghi chú |
|-------|------|-------|---------|
| `title` | string | `newspaper3k` article.title | |
| `content` | string | `newspaper3k` article.text + article.html | Văn bản thô, chưa clean |
| `url` | string | Response URL | Dùng SHA256 hash để dedup |
| `source` | string | Extract từ URL domain | `vnexpress`, `thanhnien`, `vietnamnet` |
| `author` | string | CSS selector + regex | Có thể rỗng nếu không extract được |
| `publish_date` | string | Meta tags + CSS parse | Nhiều định dạng (ISO 8601, DD/MM/YYYY) |

### Consumer → PostgreSQL (`article_metadata`) — [DEPRECATED]

Bảng staging `article_metadata` đã được loại bỏ cùng với `consumer/consumer.py` khi migrate lên AWS Serverless. ETL pipeline giờ đọc trực tiếp từ `data/articles.json` và ghi vào Star Schema. Các script init DB trong `scripts/init_db/` giữ lại bảng này cho mục đích migrate dữ liệu cũ.

```sql
-- Chỉ dùng cho migrate data cũ, không còn trong pipeline chính
CREATE TABLE article_metadata (
    id SERIAL PRIMARY KEY,
    url_hash TEXT UNIQUE,
    url TEXT,
    title TEXT,
    content TEXT,
    source TEXT,
    author TEXT,
    publish_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 2. Star Schema (PostgreSQL Data Warehouse)

Module: `database/warehouse.sql`

### Sơ đồ quan hệ

```
dim_source ─┐
             ├── fact_articles ──── fact_article_authors ──── dim_author
dim_time ────┤        │
             │        └── fact_chunks
dim_content ─┘
```

### Dimension Tables

#### `dim_source`
Nguồn báo (domain).

| Column | Type | Constraints |
|--------|------|-------------|
| `source_id` | SERIAL | PRIMARY KEY |
| `domain` | TEXT | UNIQUE |

#### `dim_time`
Thời gian xuất bản.

| Column | Type | Constraints |
|--------|------|-------------|
| `time_id` | SERIAL | PRIMARY KEY |
| `date` | DATE | UNIQUE |
| `day` | INT | |
| `month` | INT | |
| `year` | INT | |

#### `dim_content`
Nội dung bài viết gốc.

| Column | Type | Constraints |
|--------|------|-------------|
| `content_id` | SERIAL | PRIMARY KEY |
| `url_hash` | TEXT | UNIQUE |
| `content` | TEXT | |

#### `dim_author`
Tác giả.

| Column | Type | Constraints |
|--------|------|-------------|
| `author_id` | SERIAL | PRIMARY KEY |
| `author_name` | TEXT | UNIQUE |

### Fact Tables

#### `fact_articles`
Sự kiện bài viết, liên kết các dimension.

| Column | Type | Constraints |
|--------|------|-------------|
| `article_id` | SERIAL | PRIMARY KEY |
| `url_hash` | TEXT | UNIQUE |
| `title` | TEXT | |
| `source_id` | INT | FK → `dim_source(source_id)` |
| `time_id` | INT | FK → `dim_time(time_id)` |
| `content_id` | INT | FK → `dim_content(content_id)` |
| `content_length` | INT | Độ dài nội dung (ký tự) |

#### `fact_article_authors`
Quan hệ N:N giữa bài viết và tác giả.

| Column | Type | Constraints |
|--------|------|-------------|
| `article_id` | INT | FK → `fact_articles(article_id)` |
| `author_id` | INT | FK → `dim_author(author_id)` |
| | | PRIMARY KEY (`article_id`, `author_id`) |

#### `fact_chunks`
Các đoạn văn bản sau chunking, phục vụ RAG.

| Column | Type | Constraints |
|--------|------|-------------|
| `chunk_id` | SERIAL | PRIMARY KEY |
| `article_id` | INT | FK → `fact_articles(article_id)` |
| `chunk_index` | INT | Thứ tự chunk trong bài |
| `content` | TEXT | Nội dung chunk |

### Indexes

```sql
CREATE INDEX idx_source_domain ON dim_source(domain);
CREATE INDEX idx_time_date ON dim_time(date);
CREATE INDEX idx_article_hash ON fact_articles(url_hash);
CREATE INDEX idx_chunks_article ON fact_chunks(article_id);
```

---

## 3. ETL Pipeline Data Flow

Module: `etl/etl_warehouse.py`

### Input → Output mapping

```
data/articles.json (raw JSON từ crawler)
    │
    ├── Clean HTML:  regex remove tags, normalize whitespace
    ├── Remove junk:  Unicodes, special chars (Vietnamese-specific)
    ├── Chunk:        RecursiveCharacterTextSplitter (chunk_size=800, overlap=150)
    │
    ├── dim_source:     domain (tách từ URL)
    ├── dim_time:       publish_date → year/month/day
    ├── dim_content:    url_hash + raw content
    ├── dim_author:     author_name (validate length, special chars)
    ├── fact_articles:  FK → source/time/content + content_length
    ├── fact_article_authors: article_id ↔ author_id (N:N)
    └── fact_chunks:    article_id + chunk_index + content
```

### Chunking Config

| Parameter | Value |
|-----------|-------|
| Library | `langchain_text_splitters.RecursiveCharacterTextSplitter` |
| Chunk size | 800 ký tự |
| Chunk overlap | 150 ký tự |
| Separators | `["\n\n", "\n", ".", "!", "?", ",", " ", ""]` |

---

## 4. Qdrant Vector Collection

Module: `vectorize/vectorize.py`, `search/retriever.py`

### Collection Config

| Parameter | Value |
|-----------|-------|
| Collection name | `QDRANT_COLLECTION_NAME` (env) |
| Vector size | 384 (BAAI/bge-small-en-v1.5) |
| Distance metric | COSINE |
| Embedding model | `BAAI/bge-small-en-v1.5` (SentenceTransformer) |

### Point Payload

| Field | Type | Nguồn |
|-------|------|-------|
| `article_id` | int | `fact_chunks.article_id` |
| `chunk_index` | int | `fact_chunks.chunk_index` |
| `title` | str | `fact_articles.title` |
| `url` | str | Từ Star Schema JOIN |
| `content` | str | `fact_chunks.content` |
| `authors` | str | Tác giả (JOIN qua fact_article_authors) |
| `publish_timestamp` | int | Unix timestamp từ publish_date |

### UUID Generation

```python
import uuid
point_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"article_{article_id}_chunk_{chunk_index}")
```

### Batch Config

| Operation | Batch size |
|-----------|-----------|
| Embed encode | 64 chunks/batch |
| Qdrant upsert | 256 points/batch |
| Qdrant retrieve (check existing) | 1000 IDs/batch |

---

## 5. Environment Variables

Module: `search/config.py` — Pydantic Settings, đọc từ `.env`

### Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DB_NAME` | string | `newsrag` | Tên database PostgreSQL |
| `DB_USER` | string | — | User kết nối |
| `DB_PASSWORD` | string | — | Password |
| `DB_HOST` | string | `localhost` | Host (AWS: RDS endpoint) |
| `DB_PORT` | int | `5432` | Cổng kết nối |

### Kafka (v1)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | string | `localhost:9092` | Kafka broker address |
| `KAFKA_TOPIC_NEWS` | string | `news_raw` | Topic cho crawler output |

### Qdrant (v1)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `QDRANT_HOST` | string | — | Qdrant server host |
| `QDRANT_PORT` | int | `6333` | Qdrant gRPC port |
| `QDRANT_GRPC_PORT` | int | `6334` | Qdrant gRPC port (dự phòng) |
| `QDRANT_API_KEY` | string | — | API key Qdrant Cloud |
| `QDRANT_COLLECTION_NAME` | string | `news_chunks` | Collection name |

### Embedding

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EMBEDDING_MODEL` | string | `BAAI/bge-small-en-v1.5` | SentenceTransformer model |
| `EMBEDDING_SIZE` | int | `384` | Vector dimension |
| `TOP_K` | int | `20` | Số chunks trả về khi search |

### LLM Models

Mỗi model (1-3) có cấu trúc biến giống nhau:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MODEL_{N}_NAME` | string | — | Tên hiển thị (e.g., `qwen3-8b-instant`) |
| `MODEL_{N}_MODEL_ID` | string | — | Model ID cho API (e.g., `qwen/qwen3-8b-instant`) |
| `MODEL_{N}_PROVIDER` | string | — | Provider: `groq`, `google`, `ollama`, `openai` |
| `MODEL_{N}_API_KEY` | string | — | API key |
| `MODEL_{N}_TEMPERATURE` | float | `0.3` | Nhiệt độ sinh |
| `MODEL_{N}_MAX_TOKENS` | int | `2048` | Max tokens response |

### Cấu hình mặc định (`.env.example`)

```env
# Model 1: Groq Qwen3 8B (nhanh, tốt cho tiếng Việt)
MODEL_1_NAME=qwen3-8b-instant
MODEL_1_MODEL_ID=qwen/qwen3-8b-instant
MODEL_1_PROVIDER=groq

# Model 2: Groq Llama 3.1 8B (fallback)
MODEL_2_NAME=llama-3.1-8b-instant
MODEL_2_MODEL_ID=meta-llama/llama-3.1-8b-instant
MODEL_2_PROVIDER=groq

# Model 3: Google Gemini Flash (fallback cuối)
MODEL_3_NAME=gemini-2.0-flash
MODEL_3_MODEL_ID=gemini-2.0-flash
MODEL_3_PROVIDER=google

NUM_MODEL_SUPPORT=3
```

---

## 6. Pydantic Models (`search/schemas.py`)

```python
class SearchHit(BaseModel):
    id: str                   # UUID5: article_{article_id}_chunk_{chunk_index}
    title: str                # Tiêu đề bài báo
    content: str              # Nội dung chunk
    url: str                  # URL bài báo gốc
    score: float              # Cosine similarity (Qdrant)
    metadata: dict            # Payload bổ sung từ Qdrant

class GeneratorResponse(BaseModel):
    query: str                # Câu hỏi gốc
    summary: str | None       # Câu trả lời từ LLM (None nếu lỗi)
    results: list[SearchHit]  # Danh sách chunks liên quan
    total: int                # Số lượng chunks trả về
    duration_ms: float        # Thời gian xử lý (ms)
```

## 7. Quy ước mở rộng

- Tất cả dữ liệu trao đổi giữa module đều là `application/json` (Kafka message) hoặc Python object
- URL luôn được SHA256 hash để dedup xuyên suốt pipeline
- Qdrant point ID dùng UUID5 deterministic để tránh trùng lặp khi chạy lại
- Thêm module mới phải tuân theo input/output schema hiện có
