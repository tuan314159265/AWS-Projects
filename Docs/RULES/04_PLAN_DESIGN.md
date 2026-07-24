# Plan Design — News RAG Pipeline on AWS

## Giới thiệu

News RAG Pipeline là hệ thống tự động thu thập tin tức từ các báo điện tử Việt Nam, lưu trữ theo mô hình Star Schema Data Warehouse, tạo embedding vectors cho tìm kiếm ngữ nghĩa, và xây dựng hệ thống hỏi đáp RAG (Retrieval-Augmented Generation).

Dự án có **2 kiến trúc song song**:
- **v1 (Local)** — đã implement đầy đủ, chạy trên Docker Compose
- **v2 (AWS Serverless)** — chỉ mới ở mức thiết kế (`Docs/Pipeline_v3.md`), code chưa implement

---

## 1. Kiến trúc v1 (Đã implement)

### Luồng dữ liệu

```text
                          ┌─────────────────────┐
                          │    config_site.json  │
                          │   (3 news websites)  │
                          └─────────┬───────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │  Scrapy NewsRAGSpider     │
                    │  (depth-limited crawl,    │
                    │   newspaper3k parse)      │
                    └─────────────┬─────────────┘
                                  │ items (JSON)
                                  ▼
                    ┌───────────────────────────┐
                    │  KafkaPipeline            │
                    │  (confluent_kafka         │
                    │   → topic "news_raw")     │
                    └─────────────┬─────────────┘
                                  │ Kafka message
                                  ▼
                    ┌───────────────────────────┐
                    │  Kafka Consumer           │
                    │  (SHA256 hash URL,        │
                    │   insert article_metadata)│
                    └─────────────┬─────────────┘
                                  │ raw articles
                                  ▼
                    ┌───────────────────────────┐
                    │  ETL (etl_warehouse.py)   │
                    │  Clean HTML → chunk 800   │
                    │  → Star Schema INSERT     │
                    └─────────────┬─────────────┘
                                  │ clean chunks
                                  ▼
                    ┌───────────────────────────┐
                    │  Vectorize                │
                    │  (SentenceTransformer     │
                    │   → Qdrant upsert)        │
                    └─────────────┬─────────────┘
                                  │ vector search
                                  ▼
                    ┌───────────────────────────┐
                    │  RAG Engine (search/)     │
                    │  Retriever → Generator    │
                    │  (Groq/Gemini/Ollama)     │
                    └───────────────────────────┘
```

### Component Map (v1)

| Component | Công nghệ | File chính | Trạng thái |
|-----------|----------|-----------|-----------|
| Crawler | Scrapy `CrawlSpider` + newspaper3k | `crawler/spiders/spider.py` | Hoàn chỉnh |
| Stream | Kafka (KRaft, container) | `crawler/pipelines.py` | Hoàn chỉnh |
| Consumer | Python confluent_kafka | `consumer/consumer.py` | Hoàn chỉnh |
| Data Warehouse | PostgreSQL 15 (Star Schema) | `database/warehouse.sql` | Hoàn chỉnh |
| ETL | LangChain text splitter | `etl/etl_warehouse.py` | Hoàn chỉnh |
| Vector DB | Qdrant Cloud (COSINE, 384d) | `vectorize/vectorize.py` | Hoàn chỉnh |
| Embedding | SentenceTransformer (BAAI/bge-small) | `vectorize/vectorize.py` | Hoàn chỉnh |
| RAG Retriever | SentenceTransformer + Qdrant | `search/retriever.py` | Hoàn chỉnh |
| RAG Generator | LangChain + LLM API | `search/generator.py` | Hoàn chỉnh |
| LLM Providers | Groq (Qwen3, Llama3) + Gemini | `search/generator.py` | Hoàn chỉnh |
| CLI Entrypoint | Python argparse | `main.py` | Hoàn chỉnh |

---

## 2. Kiến trúc v2 (Thiết kế — Chưa implement)

Theo `Docs/Pipeline_v3.md`. Đây là mục tiêu chuyển đổi lên AWS serverless.

```text
EventBridge Scheduler (01:00, 02:00 UTC)
       │
       ├──[01:00]──► Fargate Crawler ──► SQS ──► Lambda Consumer
       │               (Scrapy Sitemap)           (SHA256 + insert Aurora)
       │
       └──[02:00]──► Lambda ETL
                       (clean → chunk → Bedrock Embed → insert Aurora pgvector)

                              ▲
                              │ top-k chunks
                     Lambda RAG API ◄── API Gateway ◄── Client
                     (Bedrock Embed query → pgvector search → Groq/Gemini LLM)
```

### Thay đổi chính v1 → v2

| Component | v1 (Local) | v2 (AWS) | Lý do |
|-----------|-----------|---------|-------|
| Crawler | Lambda timeout 15 phút | Fargate (không timeout) | Crawl được bài cũ qua sitemap |
| Stream | Kafka (tốn chi phí quản lý) | SQS (~$0/tháng) | Overkill cho pipeline nhỏ |
| Embedding | BAAI/bge-small local (384d) | Bedrock Titan Embed (1024d) | 100% AWS native, serverless |
| Vector DB | Qdrant Cloud (bên thứ ba) | Aurora PostgreSQL + pgvector | Tận dụng RDS sẵn có |
| Vectorize | Fargate riêng (~$3/tháng) | Gộp vào Lambda ETL | Giảm 1 dịch vụ |
| RAG query embed | Load model local (cold start 5-10s) | Bedrock API | Nhất quán vector space |

### Chi phí vận hành v2 (dự kiến)

| Component | Chi phí/tháng |
|-----------|--------------|
| Fargate Crawler + SQS + Lambda Consumer | ~$3-5 |
| Lambda ETL + Bedrock Titan Embed | ~$1-3 |
| Aurora Serverless v2 (2 ACU) + pgvector | ~$14 |
| Lambda RAG API + API Gateway | ~$3-4 |
| **Tổng** | **~$21-26/tháng** |

---

## 3. Component Map tổng hợp (v1 + v2)

| Module | v1 Status | v2 Status | Ghi chú |
|--------|-----------|-----------|---------|
| Crawler | Implemented (CrawlSpider) | Designed (SitemapSpider) | `spider.py` dùng `scrapy.Spider`, v2 thiết kế dùng `SitemapSpider` |
| Stream | Implemented (Kafka) | Designed (SQS) | Kafka pipeline + consumer hoạt động, SQS chưa có |
| Consumer | Implemented (Python) | Designed (Lambda) | `consumer.py` hoạt động, Lambda trigger SQS chưa code |
| Database | Implemented (Star Schema) | Designed (Aurora pgvector) | `warehouse.sql` là v1, v2 thêm pgvector extension |
| ETL | Implemented (clean+chunk) | Designed (Lambda+Bedrock) | `etl_warehouse.py` là v1 |
| Embedding | Implemented (SentenceTransformer) | Designed (Bedrock Titan) | `vectorize.py` là v1 |
| Vector DB | Implemented (Qdrant) | Designed (Aurora pgvector) | Qdrant hoạt động, pgvector chưa |
| RAG Retriever | Implemented (Qdrant search) | Designed (pgvector search) | `retriever.py` là v1 |
| RAG Generator | Implemented (Groq/Gemini/Ollama) | Same | Có thể tái sử dụng |
| Frontend | Not implemented | Designed (Next.js + FastAPI) | Không code |
| Terraform | Partial (ECS+RDS+Qdrant) | Partial | Hỗn hợp v1+v2 |

---

## 4. Migration Gaps (v1 → v2)

Những thành phần cần làm để chuyển từ v1 lên v2:

### Code cần viết mới
| Thành phần | Mô tả | Module tham chiếu |
|-----------|-------|-------------------|
| Lambda Consumer | Trigger SQS, SHA256 dedup, insert Aurora | `consumer/consumer.py` (cần Lambda port) |
| Lambda ETL | Clean → chunk → Bedrock Embed → pgvector | `etl/etl_warehouse.py` + `vectorize/vectorize.py` (gộp) |
| Lambda RAG API | Embed query → pgvector search → LLM | `search/engine.py` (cần Lambda adaptation) |
| API Gateway | REST endpoint cho RAG query | — |
| SitemapSpider | Crawl qua sitemap XML thay vì link | `crawler/spiders/spider.py` (cần spider class mới) |

### Terraform cần bổ sung
| Tài nguyên | Mô tả | Hiện trạng |
|-----------|-------|-----------|
| SQS Queue | Standard queue thay Kafka | Chưa có |
| Lambda Functions | Consumer, ETL, RAG API | Chưa có |
| Bedrock IAM Policy | Policy cho `bedrock:InvokeModel` | Chưa có |
| API Gateway | REST API endpoint | Chưa có |
| Secrets Manager | Lưu DB credentials | Chưa có |

### Config cần sửa
| File | Vấn đề | Hướng xử lý |
|------|--------|-------------|
| `main.tf` | `common_env` chứa Kafka + Qdrant vars cho cloud deploy | Cần tách biệt local/cloud environment blocks |
| `docker-compose.yml` | Thiếu Qdrant service | Thêm Qdrant container hoặc ghi rõ trong docs |
| `.env.example` | Còn Qdrant config cho v2 (mặc dù v2 dùng pgvector) | Có thể giữ làm fallback hoặc loại bỏ |

### Makefile drift
| Target | Vấn đề |
|--------|--------|
| `test-interactive` | Trỏ đến `tests.search.test_interactive` — file không tồn tại |
| `test-gen` | Trỏ đến `tests.search.test_generator` — file không tồn tại |
| `run-fastapi` | Trỏ đến `app.api:app` — module không tồn tại |
| `crawl` | Chạy Scrapy trực tiếp, không qua `main.py` — có thể gây nhầm lẫn |

---

## 5. Configuration Model

```text
.env (file)
  │
  ▼
pydantic_settings (search/config.py)
  │
  ├── ModelConfig      → embedding model, top_k
  ├── LLMConfig        → model list từ MODEL_1/2/3 env vars
  └── SearchConfig     → Qdrant connection
        │
        ▼
search/retriever.py   → Retriever singleton (dùng ModelConfig + SearchConfig)
search/generator.py   → GeneratorRegistry singleton (dùng LLMConfig)
    │
    ▼
search/engine.py      → Pipeline.ask() (phối hợp Retriever + GeneratorRegistry)
```

### Singleton Pattern

| Singleton | File | Khởi tạo |
|-----------|------|---------|
| `settings` | `search/config.py` | `Settings(_env_file=".env")` |
| `Retriever` | `search/retriever.py` | Lazy load: model + QdrantClient |
| `GeneratorRegistry` | `search/generator.py` | Lazy load: đọc LLMConfig, build providers |

---

## 6. Prompt System

Module: `search/prompts.py`

| Prompt | Mục đích |
|--------|---------|
| `NEWS_RAG_SYSTEM_PROMPT` | "Bạn là chuyên gia phân tích tin tức..." — yêu cầu trích dẫn nguồn, khách quan, từ chối nếu thiếu context |
| `NEWS_RAG_HUMAN_PROMPT` | Template: "Ngữ cảnh tin tức: ... Câu hỏi: ..." |
| `VANILLA_SYSTEM_PROMPT` | System prompt đơn giản (không RAG) |
| `VANILLA_HUMAN_PROMPT` | Human prompt đơn giản |

Generator dùng `ChatPromptTemplate` từ LangChain, output qua `StrOutputParser`. Kết quả được strip thẻ `\` trước khi trả về.

---

## 7. Prompt Engineering Tips

### Xử lý response

```python
# Generator tự động strip <think> tags (dùng cho reasoning model)
response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
```

### Fallback LLM chain

Pipeline hiện tại dùng cơ chế fallback: model chính → model phụ → thông báo lỗi. Thứ tự fallback mặc định theo thứ tự trong `LLMConfig` (thường là Qwen3 → Gemini → error).

---

## 8. Hướng phát triển

### Ngắn hạn (v1 improvements)
- Thêm Qdrant service vào `docker-compose.yml`
- Tạo test files cho search engine (hiện tại Makefile trỏ đến file không tồn tại)
- Dọn dẹp Makefile targets không dùng đến

### Trung hạn (v2 migration)
- Implement Lambda Consumer + ETL + RAG API
- Bổ sung SQS, Lambda resources vào Terraform
- Thay thế Qdrant env vars bằng Aurora pgvector config
- Thêm Bedrock IAM policy

### Dài hạn
- Frontend (Next.js + FastAPI)
- GitHub Actions CI/CD
- Integration tests
- Monitoring & alerting
