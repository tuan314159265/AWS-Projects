# Naming & Coding Convention — News RAG Pipeline on AWS

## Environment Setup
- File: `.env` (root project)
- Luôn có bản mẫu `.env.example` commit lên git
- Không commit `.env` thật (chỉ `.env.example`)
- Khi deploy, copy `.env.example` thành `.env` và điền giá trị thật

---

## Ngôn ngữ trong code
- **Code identifiers** (tên hàm, biến, class, file, module): Tiếng Anh — `NewsRAGSpider`, `run_etl_warehouse`, `config_site.json`
- **Comments & log messages**: Tiếng Việt — `# Chạy spider trong process riêng`, `print("[Consumer] Đang khởi tạo kết nối...")`
- **Print/user-facing strings**: Tiếng Việt
- **Config JSON keys**: Tiếng Anh (`url`, `source`, `content`, `title`)

---

## Python — File & Folder

- File/Tên module: phản ánh chức năng, viết liền hoặc gạch dưới — `consumer.py`, `etl_warehouse.py`, `logger_setup.py`, `generator.py`
- Folder: ngắn gọn, 1 từ — `crawler/`, `search/`, `etl/`, `vectorize/`, `consumer/`

### Hàm

- Hàm public: tiếng Anh, mô tả hành động — `run_spider()`, `run_consumer()`, `clean_text()`, `start_processing()`
- Hàm private/xử lý nội bộ: prefix `_` — `_init_llm()`, `_format_context()`, `_initialize()`, `_reconnect()`
- Hàm main: `do_*()` cho stage (`do_crawl_stage()`), `run_*()` cho module entry (`run_etl_warehouse()`)
- Callback Kafka consumer: `def handler()` (theo interface của `confluent_kafka`)

### Class

- Tên class: PascalCase — `NewsRAGSpider`, `KafkaPipeline`, `BaseGenerator`, `GeneratorRegistry`, `Retriever`
- Pydantic models: PascalCase — `SearchHit`, `GeneratorResponse`, `ModelConfig`, `LLMInstanceConfig`

### Biến môi trường

- `UPPER_CASE` — `DB_NAME`, `KAFKA_BOOTSTRAP_SERVERS`, `MODEL_1_API_KEY`, `EMBEDDING_MODEL`
- Model config có cấu trúc: `MODEL_{N}_{PROPERTY}` — `MODEL_1_NAME`, `MODEL_1_PROVIDER`, `MODEL_1_TEMPERATURE`

---

## SQL (Data Warehouse)

Tuân theo `database/warehouse.sql`:

- Table prefix: `dim_*` (dimension), `fact_*` (fact)
- Column: gạch dưới — `url_hash`, `content_id`, `author_name`, `publish_date`
- Primary key: `{table}_id` — `source_id`, `article_id`, `chunk_id`
- Foreign key: trùng tên PK bảng tham chiếu

---

## Terraform (`main.tf`)

- Resource name tag: prefix `newsrag-` — `newsrag-vpc`, `newsrag-cluster`, `newsrag-postgres`
- Variable: `db_password`, `qdrant_host`, `model_1_api_key`

---

## Git Convention

### Commit Message
```
[feat] thêm tính năng X
[fix] sửa lỗi Y
[refactor] cải thiện module Z
[docs] cập nhật tài liệu
[chore] cập nhật dependencies, config
```

- Dùng imperative mood (thêm, sửa, cập nhật — không "đã thêm", "đã sửa")
- Nếu cần giải thích, thêm body sau 1 dòng trống:
  ```
  [feat] chunk text bằng LangChain RecursiveCharacterTextSplitter

  Thay thế split cố định bằng sliding window 800/150.
  Giúp context overlap tốt hơn cho RAG retrieval.
  ```

### Branch
- `main` — ổn định, đã deploy hoặc sẵn sàng deploy
- `dev` — phát triển chung, tạo PR vào `dev` để review
- `feat/<module>` — tính năng mới (vd: `feat/aws-lambda-etl`)
- `fix/<bug>` — sửa lỗi (vd: `fix/kafka-reconnect`)

### Workflow cơ bản
```
dev ───► feat/xxx ───► dev ───► main
```
1. Branch từ `dev`, làm tính năng trên `feat/xxx`
2. Tạo PR vào `dev`, squash merge
3. `dev` chạy ổn định → merge vào `main`

### Quy tắc quản lý

#### Nội dung commit
- **Atomic**: mỗi commit một thay đổi logic duy nhất — không gộp "sửa lỗi + refactor + thêm tính năng" vào 1 commit
- **Không commit**: `.env`, `terraform.tfvars` (chứa secrets), `*.log`, `model_cache/`, `data/`, `__pycache__/`, `.terraform/`, `terraform.tfstate*`
- **File mới phát sinh**: nếu pipeline tạo ra file log, output, cache — cập nhật `.gitignore` ngay trong commit đó

#### Giữ repo sạch
- **Không commit model binary**: SentenceTransformer model cache không được đẩy lên git. Dùng `model_cache/` trong `.gitignore`, load model động qua `sentence-transformers` khi chạy.
- **Không commit data samples**: file JSON output crawl thử, SQL dump, Qdrant backup — chỉ commit schema và config.
- **`.gitignore` hygiene**: khi thêm dependency sinh file mới (log, cache, output), kiểm tra và cập nhật `.gitignore` cùng lúc.

#### Review
- **Tạo PR cho mọi thay đổi** trên `dev` — dự án nhỏ nhưng vẫn review
- **Squash merge** khi merge feature branch vào `dev` để giữ lịch sử sạch

#### Git tags
- Dùng `v{major}.{minor}` cho release — `v1.0`, `v1.1`
- Mỗi tag đi kèm mô tả ngắn gọn bằng tiếng Việt

#### Changelog (`CHANGELOG.md`)
- File `CHANGELOG.md` ở thư mục gốc, duy trì xuyên suốt dự án
- Format theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), version theo [SemVer](https://semver.org/)
- Mỗi milestone/release tổng hợp các thay đổi chính, phân loại:
  - `### Added` — tính năng mới
  - `### Changed` — thay đổi trên code hiện tại
  - `### Fixed` — sửa lỗi
  - `### Removed` — xoá bỏ tính năng
- Cập nhật CHANGELOG ngay trong commit của milestone, trước khi tag release
