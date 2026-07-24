# Hướng dẫn sử dụng — News RAG Pipeline on AWS

## 1. Giới thiệu

News RAG Pipeline là hệ thống tự động thu thập tin tức từ các báo điện tử Việt Nam (VnExpress, Thanh Niên, VietnamNet), xử lý và lưu trữ theo mô hình Star Schema, tạo vector embeddings, và cho phép hỏi đáp thông minh dựa trên ngữ cảnh tin tức (RAG).

---

## 2. Yêu cầu hệ thống

- Python 3.10+
- Docker & Docker Compose
- Git
- Qdrant Cloud account (hoặc Qdrant local instance)
- API keys: Groq, Google Gemini (tuỳ chọn: Ollama local)

---

## 3. Cài đặt nhanh

### Bước 1: Clone và setup môi trường

```bash
git clone git@github.com:tuan314159265/AWS-Projects.git
cd AWS-Projects
make setup
```

### Bước 2: Khởi chạy infrastructure local

```bash
docker compose up -d
```

Khởi động:
- **Kafka** (KRaft mode, port 9092) — message broker cho crawler output
- **PostgreSQL 15** (port 5432) — database cho Star Schema

> **Lưu ý:** `docker-compose.yml` hiện tại **không** bao gồm Qdrant. Bạn cần chạy Qdrant riêng (cloud hoặc `docker run qdrant/qdrant`).

### Bước 3: Cấu hình môi trường

```bash
cp .env.example .env
# Điền các giá trị thật vào .env:
# - DB_HOST, DB_USER, DB_PASSWORD
# - QDRANT_HOST, QDRANT_API_KEY, QDRANT_COLLECTION_NAME
# - GROQ_API_KEY, GEMINI_API_KEY (nếu dùng)
```

### Bước 4: Tạo database schema

```bash
# Kết nối PostgreSQL và chạy:
psql -h localhost -U postgres -d newsrag -f database/warehouse.sql
```

---

## 4. Pipeline Modes

### Crawl — Thu thập tin tức

```bash
python main.py --mode crawl
```

Chạy `NewsRAGSpider` trên 3 trang báo song song, đẩy dữ liệu qua Kafka vào bảng `article_metadata`.

**Luồng xử lý:**
1. Khởi chạy Kafka Consumer (process riêng)
2. Chạy 3 Scrapy spiders (mỗi URL một process)
3. Mỗi spider crawl link depth-limited (tối đa 5), parse bằng newspaper3k
4. Item Pipeline đẩy JSON vào Kafka topic `news_raw`
5. Consumer đọc Kafka, SHA256 hash URL, insert vào PostgreSQL

### ETL — Xử lý vào Star Schema

```bash
python main.py --mode etl
```

Đọc `article_metadata`, làm sạch HTML, chunk văn bản (800 ký tự, overlap 150), insert vào Star Schema.

**Luồng xử lý:**
1. Load schema (`database/warehouse.sql`) nếu chưa có
2. Đọc articles từ `article_metadata` (có flag `processed = false`)
3. Clean HTML: regex remove tags, normalize whitespace
4. Chunk: `RecursiveCharacterTextSplitter` (800/150)
5. Map vào dimension tables + fact tables
6. Batch commit mỗi 50 records

### Vectorize — Embedding vào Qdrant

```bash
python main.py --mode vectorize
```

Đọc chunks từ Star Schema, dùng SentenceTransformer (`BAAI/bge-small-en-v1.5`) tạo vector 384 chiều, upsert vào Qdrant.

**Luồng xử lý:**
1. Kết nối PostgreSQL, JOIN qua Star Schema lấy chunks + metadata
2. Tạo UUID5 deterministic cho mỗi chunk
3. Kiểm tra Qdrant để skip chunks đã tồn tại
4. Encode batch 64 chunks → vector 384-dim
5. Upsert Qdrant batch 256 points

### Full Pipeline

```bash
python main.py --mode full
```

Chạy tuần tự: **crawl → etl → vectorize** (tự động luân phiên ETL và vectorize đến khi hết dữ liệu mới).

### Auto Mode

```bash
python main.py --mode auto
```

Lên lịch chạy full pipeline 3 lần/ngày: 08:00, 14:00, 20:00. Giữ process chạy nền.

---

## 5. RAG Query

### CLI testing

```bash
make test-interactive
```

**Lưu ý:** Target `test-interactive` hiện tại trỏ đến file `tests/search/test_interactive.py` chưa tồn tại. Để test RAG thủ công:

```python
from search.engine import Pipeline

pipeline = Pipeline()
result = pipeline.ask("Tin tức về AI mới nhất?")
print(result.summary)
```

### API từ Python

```python
from search.engine import Pipeline

# Query với model mặc định (Qwen3-8B)
resp = Pipeline().ask("Giá xăng dầu hôm nay thế nào?")
print(f"Trả lời: {resp.summary}")
print(f"Số chunks: {resp.total}")
print(f"Thời gian: {resp.duration_ms}ms")

# Query với model cụ thể
resp = Pipeline().ask("AI 2026 có gì mới?", model="gemini-2.0-flash")

# Query không dùng RAG (raw LLM)
resp = Pipeline().ask("Viết đoạn văn về Hà Nội", is_vanilla=True)
```

### Multi-model fallback

Generator tự động fallback qua các model nếu model chính lỗi:
```python
from search.generator import GeneratorRegistry

registry = GeneratorRegistry()
# Thứ tự: model chính → fallback list → "Xin lỗi..."
response = registry.generate_with_fallback(
    query="Thời tiết hôm nay?",
    hits=search_results,
    identifier="qwen3-8b-instant",
    fallback_identifiers=["gemini-2.0-flash"]
)
```

---

## 6. Makefile Targets

| Target | Command | Mô tả |
|--------|---------|-------|
| `setup` | `make setup` | Tạo venv + pip install -r requirements.txt |
| `up` | `make up` | `docker compose up -d` (Kafka + PostgreSQL) |
| `down` | `make down` | `docker compose down` |
| `restart` | `make restart` | down + up |
| `crawl` | `make crawl` | Chạy Scrapy trực tiếp (không qua Kafka) |
| `full` | `make full` | `python main.py --mode full` |
| `auto` | `make auto` | `python main.py --mode auto` (3 ca/ngày) |
| `run-crawl` | `make run-crawl` | `python main.py --mode crawl` |
| `run-etl` | `make run-etl` | `python main.py --mode etl` |
| `run-vectorize` | `make run-vectorize` | `python main.py --mode vectorize` |
| `clean` | `make clean` | Xoá toàn bộ `__pycache__` |

---

## 7. Kiến trúc dữ liệu

### Luồng dữ liệu tổng quan

```text
Báo điện tử → Crawler → Kafka → Consumer → PostgreSQL (raw)
                                                  ↓
                                            ETL (clean + chunk)
                                                  ↓
                                    Star Schema (PostgreSQL)
                                                  ↓
                                    SentenceTransformer → Qdrant (vectors)
                                                  ↓
                                    RAG: Qdrant search + LLM → trả lời
```

### Cấu trúc database

Star Schema gồm:
- **Dimension tables**: `dim_source`, `dim_time`, `dim_content`, `dim_author`
- **Fact tables**: `fact_articles`, `fact_article_authors`, `fact_chunks`

Chi tiết xem `Docs/03_DATA_SCHEMA.md`.

---

## 8. Triển khai AWS (Terraform)

### Bước 1: Cấu hình AWS

```bash
aws configure
```

### Bước 2: Deploy infrastructure

```bash
terraform init
terraform apply
```

Tạo:
- VPC + Subnets + Internet Gateway
- Aurora Serverless v2 PostgreSQL (db.t4g.medium)
- ECR repository + ECS Cluster
- 3 ECS Task Definitions (crawler, etl, vectorize)
- EventBridge Scheduler (01:00, 02:00, 03:00 UTC)

### Bước 3: Build và push Docker image

```bash
./deploy.sh
```

Script tự động: `terraform apply` → ECR login → `docker build` → `docker tag` → `docker push`.

> **Lưu ý quan trọng:** Terraform hiện tại đang ở trạng thái **hỗn hợp v1/v2**. Environment variables trong ECS task definitions vẫn tham chiếu Qdrant Cloud và Kafka (localhost:9092) — chưa phù hợp cho production v2 thuần tuý. Các thành phần v2 (SQS, Lambda, Bedrock, API Gateway) chưa có trong Terraform. Xem `Docs/04_PLAN_DESIGN.md` để biết migration gaps chi tiết.

---

## 9. Biến môi trường

Copy `.env.example` → `.env` và điền:

```env
# Database
DB_NAME=newsrag
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Qdrant (Vector DB)
QDRANT_HOST=your-instance.qdrant.io
QDRANT_API_KEY=your_key
QDRANT_COLLECTION_NAME=news_chunks

# LLM API Keys
GROQ_API_KEY=gsk_your_key
GOOGLE_API_KEY=AIza_your_key
```

---

## 10. Gợi ý quy trình sử dụng

1. **Setup**: `make setup && docker compose up -d`
2. **Crawl**: `python main.py --mode crawl` (thu thập tin tức)
3. **ETL**: `python main.py --mode etl` (xử lý vào Star Schema)
4. **Vectorize**: `python main.py --mode vectorize` (tạo embeddings)
5. **Hỏi đáp**: Dùng Python import `search.engine.Pipeline` để query

Hoặc chạy một lệnh duy nhất: `python main.py --mode full`

Lên lịch tự động: `python main.py --mode auto` (chạy nền, 3 ca/ngày)
