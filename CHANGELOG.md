# Changelog

All notable changes to this project will be documented in this file.

Format dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
và theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-07-27

### Changed
- **Frontend migration: Next.js 16 (Turbopack) → Vite + React + React Router**
  - Xoá toàn bộ Next.js API routes (`frontend/src/app/api/`) — backend FastAPI đã có endpoint tương đương
  - `vite.config.ts`: proxy `/api` → `http://localhost:8000`, `appType: 'spa'` cho history fallback
  - `package.json`: xoá `next`, `pg`, `@aws-sdk/client-bedrock-runtime`, `@types/node`, `@types/pg`; thêm `vite`, `@vitejs/plugin-react`, `react-router-dom`
  - `index.html` entry point, `main.tsx` routing với `BrowserRouter`
  - `Layout.tsx` + `Outlet`, `Sidebar.tsx` dùng `<Link to={...}>` (không còn `href`)

### Fixed
- **Sidebar navigation broken**: `href` → `to` prop cho react-router-dom Link
- **Vite SPA 404 on refresh**: thêm `appType: 'spa'` trong `vite.config.ts`
- **Orphan vectors in pgvector**: 120 vectors trong `fact_vectors` không match `fact_chunks` (stale data từ pipeline cũ)
  - `DELETE FROM fact_vectors WHERE chunk_id NOT IN (SELECT chunk_id FROM fact_chunks);`
  - Chạy lại `make vectorize` → 500 vectors mới
- **Retriever.search() trả về `None`**: thiếu `return search_hits` sau vòng lặp for trong `search/retriever.py:61`
- **LLM model Legacy/EOL**:
  - `anthropic.claude-3-haiku-20240307-v1:0` → Legacy (unused 30 days)
  - `anthropic.claude-3-5-sonnet-20241022-v2:0` → End of life
  - Fallback chain: Bedrock Sonnet 4 (non-streaming) → Groq `gpt-oss-120b` (streaming OK)
  - Cập nhật `.env`: `gpt-oss-120b` làm default đầu tiên

### Added
- `make vectorize` target trong Makefile
- Backend health check `/health` trả về `initializing` cho đến khi pipeline ready

---

## [1.1.0] - 2026-07-27

### Added
- File `CHANGELOG.md` — nhật ký thay đổi dự án
- Sắp xếp lại cấu trúc thư mục: gom tài liệu vào `Docs/`, script vào `scripts/`

### Removed
- **Xoá `consumer/consumer.py`** và luồng Kafka → `article_metadata` staging table.
  Lý do: Architecture chuyển từ v1 (Kafka + Consumer độc lập) lên v2 (AWS Serverless). Bảng `article_metadata` là tầng staging trung gian gây trùng lặp dữ liệu với Star Schema, cần thêm bước migrate và không cần thiết khi ETL pipeline đã ghi trực tiếp vào Star Schema (`fact_articles`, `fact_chunks`). Các script init DB giữ lại `article_metadata` cho mục đích migrate dữ liệu cũ.

### Fixed
- Hardcode CloudWatch region thành `ap-southeast-2` cho monitoring client

---

## [1.0.0] - 2026-07-25

### Added
- **SSE streaming** — dashboard real-time qua Server-Sent Events
- **API client** (`frontend/src/lib/api.ts`) — kết nối frontend với backend API
- **CI/CD pipeline** qua GitHub Actions (deploy backend, frontend, monitoring)
- **CloudWatch monitoring** — dashboard AWS CloudWatch cho pipeline metrics
- **Frontend dashboard** (Next.js App Router + TypeScript + Tailwind):
  - Dashboard overview
  - Article explorer
  - Chat interface
  - Search page
  - Pipeline monitor
- **API routes** (Next.js API routes):
  - `GET /api/articles` — danh sách articles
  - `GET /api/articles/[id]/chunks` — chunks của article
  - `GET /api/search` — tìm kiếm RAG
  - `GET /api/stats` — thống kê pipeline
  - `GET /api/pipeline/status` — trạng thái pipeline
- **Sidebar component** điều hướng dashboard
- **StatCard component** hiển thị KPI
- **Zustand store** cho state management frontend

### Changed
- **Migrate to AWS Serverless architecture**:
  - Thêm Lambda handlers: `lambda_handlers/consumer`, `etl`, `search_api`
  - API Gateway integration
  - AWS SQS thay thế Kafka (song song với v1)
  - Terraform cập nhật cho v2 (ECS Fargate, EventBridge, SQS)
- Cập nhật `Makefile` hỗ trợ cả local dev (v1) và AWS deploy (v2)
- Tái cấu trúc project thành full-stack architecture

### Fixed
- Khôi phục dấu tiếng Việt trong pipeline xử lý
- `CREATE TABLE IF NOT EXISTS` cho `article_metadata` trong consumer

---

## [0.2.0] - 2026-07-23

### Added
- **Hệ thống tài liệu kiến trúc**:
  - `Docs/Pipeline_v3.md` — thiết kế kiến trúc AWS Serverless v2
  - `Docs/RULES/00_PROJECT_STRUCTURE.md` — cấu trúc thư mục
  - `Docs/RULES/01_NAMING_CONVENTION.md` — quy tắc đặt tên, Git convention
  - `Docs/RULES/02_API_SPEC.md` — CLI & module interface
  - `Docs/RULES/03_DATA_SCHEMA.md` — schema dữ liệu
  - `Docs/RULES/04_PLAN_DESIGN.md` — kiến trúc tổng thể, migration gaps
  - `Docs/RULES/USER_GUIDE.md` — hướng dẫn sử dụng pipeline

### Changed
- Cập nhật component pipeline: consumer, search engine
- Phân tách rõ v1 (Local) / v2 (AWS Serverless) trong tài liệu

---

## [0.1.0] - 2026-06-22

### Added
- **Khởi tạo dự án** — News RAG Pipeline on AWS
- **Crawler** (Scrapy): crawl tin tức từ thanhnien.vn, vnexpress.net, vietnamnet.vn
- **ETL pipeline**: làm sạch HTML, chunk văn bản, insert vào Star Schema (PostgreSQL)
- **Kafka integration**: producer (crawler → topic `news_raw`) + consumer (topic → PostgreSQL)
- **Vector embedding** — SentenceTransformer embed chunks → Qdrant upsert
- **RAG Engine**:
  - Retriever (SentenceTransformer + Qdrant vector search)
  - Generator (4 providers: Groq, Google Gemini, Ollama, OpenAI)
  - Pipeline.ask() orchestration với fallback chain
- **Star Schema** database: `dim_source`, `dim_time`, `dim_content`, `dim_author`, `fact_articles`, `fact_article_authors`, `fact_chunks`
- **Docker Compose**: Kafka (KRaft) + PostgreSQL 15
- **Terraform**: VPC, Aurora, ECR, ECS Fargate, EventBridge
- **CLI entrypoint** (`main.py`): modes crawl, etl, vectorize, full, auto
- **Scripts**: `deploy.sh` build & push Docker image lên ECR
- **Config**: `config_site.json` danh sách URL báo
