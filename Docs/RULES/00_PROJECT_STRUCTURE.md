# Cấu trúc dự án — News RAG Pipeline on AWS

> **Ghi chú kiến trúc:** Dự án có 2 luồng kiến trúc song song. **v1 (Local)** đã implement đầy đủ. **v2 (AWS Serverless)** chỉ mới ở mức thiết kế trong `Docs/Pipeline_v3.md`, chưa có code tương ứng. Các module được gắn nhãn `[v1]` / `[v2]` / `[v1+v2]` để phân biệt.

```text
AWS-Projects/
│
├── config/                                   # Cấu hình đầu vào
│   └── config_site.json                      # [v1] Danh sách URL báo cần crawl (thanhnien, vnexpress, vietnamnet)
│
├── consumer/                                 # [v1] Kafka Consumer
│   ├── __init__.py
│   └── consumer.py                           # Đọc Kafka topic news_raw, SHA256 hash URL, insert vào article_metadata
│
├── crawler/                                  # [v1] Scrapy Crawler
│   ├── __init__.py
│   ├── pipelines.py                          # Item Pipeline: đẩy bài đã crawl vào Kafka topic news_raw
│   ├── settings.py                           # Scrapy settings: pipeline priority, user-agent, robotstxt
│   └── spiders/
│       ├── __init__.py
│       └── spider.py                         # NewsRAGSpider: crawl link depth-limited, parse bằng newspaper3k
│
├── database/                                 # [v1] Star Schema Data Warehouse
│   └── warehouse.sql                         # DDL: dim_source, dim_time, dim_content, dim_author, fact_articles, fact_article_authors, fact_chunks
│
├── Docs/                                     # Tài liệu dự án
│   ├── 00_PROJECT_STRUCTURE.md               # File này — cấu trúc thư mục
│   ├── 01_NAMING_CONVENTION.md               # Quy tắc đặt tên, Git convention
│   ├── 02_API_SPEC.md                        # CLI interface & Module interface
│   ├── 03_DATA_SCHEMA.md                     # Star Schema, Qdrant payload, Pydantic models, env vars
│   ├── 04_PLAN_DESIGN.md                     # Kiến trúc tổng thể, component map, migration gaps
│   ├── Pipeline_v3.md                        # [v2 DESIGN] Thiết kế kiến trúc AWS Serverless v2 (đã có từ trước)
│   └── USER_GUIDE.md                         # Hướng dẫn sử dụng và chạy pipeline
│
├── etl/                                      # [v1] ETL: làm sạch + chunk → Star Schema
│   ├── __init__.py
│   └── etl_warehouse.py                      # Clean HTML, chunk văn bản, insert vào Star Schema
│
├── search/                                   # [v1] RAG Engine
│   ├── __init__.py
│   ├── config.py                             # Pydantic Settings: ModelConfig, LLMConfig, SearchConfig
│   ├── engine.py                             # Pipeline.ask(): retriever → generator orchestration
│   ├── generator.py                          # BaseGenerator + 4 providers (Groq, Google, Ollama, OpenAI) + GeneratorRegistry
│   ├── logger_setup.py                       # Rotating file + stdout logger
│   ├── prompts.py                            # System/human prompts cho RAG (tiếng Việt)
│   ├── retriever.py                          # SentenceTransformer embed + Qdrant vector search
│   └── schemas.py                            # Pydantic models: SearchHit, GeneratorResponse
│
├── vectorize/                                # [v1] Vector Embedding
│   ├── __init__.py
│   └── vectorize.py                          # SentenceTransformer embed chunks → Qdrant upsert
│
├── .env.example                              # Mẫu biến môi trường (DB, Kafka, Qdrant, LLM keys)
├── .gitignore                                # Ignores venv, __pycache__, .env, terraform, model_cache
├── deploy.sh                                 # Script deploy: terraform apply → docker build/push → ECR
├── docker-compose.yml                        # [v1] Local infra: Kafka (KRaft) + PostgreSQL 15
├── Dockerfile                                # Container image: python:3.10-slim, cài đặt dependencies
├── main.py                                   # Entrypoint CLI: --mode {crawl, etl, vectorize, full, auto}
├── main.tf                                   # [v1+v2] Terraform: VPC, Aurora, ECR, ECS Fargate, EventBridge
├── Makefile                                  # Targets: setup, up/down, crawl, etl, vectorize, test-interactive
├── README.md                                 # Tổng quan dự án (tiếng Việt)
├── requirements.txt                          # Python dependencies (scrapy, kafka, sentence-transformers, langchain...)
└── terraform.tfvars                          # Biến Terraform (placeholders)
```

---

## Chi tiết module

### `config/config_site.json`
Danh sách URL gốc cho crawler. Định dạng JSON array. Hiện tại gồm 3 trang báo:
- `https://thanhnien.vn/`
- `https://vnexpress.net/`
- `https://vietnamnet.vn/`

### `consumer/consumer.py` `[v1]`
Kafka Consumer độc lập. Đọc từ topic `news_raw`, decode JSON message, SHA256 hash URL để dedup, insert vào bảng `article_metadata` trong PostgreSQL. Xử lý reconnect khi mất kết nối.

### `crawler/spiders/spider.py` `[v1]`
`NewsRAGSpider` kế thừa `scrapy.Spider` (không phải `SitemapSpider`). Đọc URL từ `config_site.json`, crawl link trong nội dung (depth limit = 5), parse bài viết bằng `newspaper3k`. Trích xuất tác giả qua CSS selector + regex, ngày xuất bản từ nhiều dạng meta tags.

### `database/warehouse.sql` `[v1]`
Star Schema gồm 4 dimension tables và 3 fact tables.

### `search/` `[v1]`
Module RAG hoàn chỉnh. `Pipeline.ask()` nhận câu hỏi → `Retriever` search Qdrant → `Generator` gọi LLM (Groq/Gemini/Ollama) → trả `GeneratorResponse`. Hỗ trợ fallback chain qua nhiều model.

### `main.tf` `[v1+v2]`
Terraform hỗn hợp: định nghĩa VPC, Aurora PostgreSQL, ECR, ECS Fargate tasks (crawler/etl/vectorize) và EventBridge Scheduler. Tuy nhiên env vars vẫn tham chiếu Qdrant cloud và Kafka local — chưa được cập nhật cho v2 thuần túy.

---

## Những thành phần CHƯA có

| Thành phần | Trạng thái | Ghi chú |
|-----------|-----------|---------|
| **Frontend** (Next.js + FastAPI) | Chưa code | Được thiết kế trong `Pipeline_v3.md`, chưa có thư mục `frontend/` hay `app/` |
| **Tests** | Chưa có | `Makefile` tham chiếu `tests/search/test_interactive` và `tests/search/test_generator` nhưng không tồn tại |
| **Qdrant trong docker-compose** | Thiếu | `docker-compose.yml` chỉ có Kafka + PostgreSQL. Cần Qdrant riêng (cloud hoặc local docker run) |
| **v2 Lambda functions** | Chưa code | Consumer, ETL, RAG API dạng Lambda chưa implement |
| **SQS resources trong Terraform** | Chưa có | v2 thiết kế dùng SQS thay Kafka nhưng chưa có trong `main.tf` |
| **Bedrock IAM policy** | Chưa có | v2 dùng Bedrock Titan Embed nhưng Terraform chưa có policy tương ứng |
