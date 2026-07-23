# News RAG Pipeline on AWS — AWS Internship Project

## Giới thiệu dự án
Dự án **News RAG Pipeline on AWS** được xây dựng trong khuôn khổ chương trình thực tập AWS (AWS Internship Project). Mục tiêu chính là thiết kế và triển khai một hệ thống xử lý dữ liệu lớn (Big Data Pipeline) tự động thu thập tin tức, lưu trữ vào mô hình Data Warehouse (Star Schema), tạo embedding vectors và xây dựng công cụ hỏi đáp thông minh sử dụng kiến trúc RAG (Retrieval-Augmented Generation) hoạt động serverless hoàn toàn trên nền tảng AWS.

Dự án hỗ trợ hai kiến trúc chính:
1. **Môi trường cục bộ (Local Development)**: Sử dụng Docker Compose giả lập Kafka để stream dữ liệu, PostgreSQL cho Data Warehouse, SentenceTransformer để tạo vector embeddings local và Qdrant làm Vector Database.
2. **Môi trường AWS Cloud (Production v2)**: Chuyển đổi toàn bộ sang serverless với Amazon ECS Fargate cho Crawler, SQS thay thế Kafka, AWS Lambda xử lý Consumer/ETL, Amazon Bedrock sinh vector embeddings và Amazon Aurora Serverless v2 PostgreSQL tích hợp extension pgvector để làm kho dữ liệu kiêm Vector Database giúp tối ưu hóa chi phí.

---

## Cấu trúc thư mục dự án (Project Directory Tree)

Dưới đây là cấu trúc thư mục chi tiết của dự án:

```text
├── config
│   └── config_site.json          # Cấu hình danh sách tên miền và link báo cần cào
├── consumer
│   ├── consumer.py               # Kafka consumer nhận dữ liệu thô ghi vào PostgreSQL
│   └── __init__.py
├── crawler
│   ├── __init__.py
│   ├── pipelines.py              # Đẩy tin tức đã cào từ Scrapy vào Kafka Broker
│   ├── settings.py               # Cấu hình tần suất cào, user-agent của Scrapy
│   └── spiders
│       ├── __init__.py
│       └── spider.py             # Tin tức sitemap/link crawler sử dụng BeautifulSoup/Newspaper3k
├── database
│   └── warehouse.sql             # SQL Schema định nghĩa cấu trúc dữ liệu Star Schema
├── deploy.sh                     # Shell script tự động hóa đóng gói và triển khai Lambda
├── docker-compose.yml            # Khởi chạy Kafka, Zookeeper, PostgreSQL và Qdrant local
├── Dockerfile                    # Đóng gói crawler, etl, vectorize chạy trên ECS Fargate
├── Docs
│   └── Pipeline_v3.md            # Tài liệu phân tích thiết kế, chi tiết kỹ thuật hệ thống v2
├── etl
│   ├── etl_warehouse.py          # Làm sạch dữ liệu, phân tách dữ liệu thô vào Star Schema
│   └── __init__.py
├── main.py                       # File entrypoint chính để điều hướng các tác vụ (mode) chạy
├── main.tf                       # Terraform script định nghĩa hạ tầng AWS
├── Makefile                      # Định nghĩa các macro cài đặt và test nhanh ứng dụng
├── README.md                     # Tài liệu hướng dẫn sử dụng và giới thiệu dự án
├── requirements.txt              # Danh sách thư viện Python cần thiết
├── search                        # RAG engine tìm kiếm và sinh câu trả lời
│   ├── config.py                 # Đọc cấu hình kết nối DB, API keys bằng Pydantic Settings
│   ├── engine.py                 # RAG Pipeline tích hợp Retriever và Generator
│   ├── generator.py              # Generator gọi API LLM (Groq Qwen/Llama, Gemini)
│   ├── __init__.py
│   ├── logger_setup.py           # Cấu hình hệ thống log
│   ├── prompts.py                # Định nghĩa hệ thống prompt cho RAG
│   ├── retriever.py              # Thực hiện tìm kiếm vector tương đồng trên Qdrant DB
│   └── schemas.py                # Định nghĩa kiểu dữ liệu (data models) bằng Pydantic
├── terraform.tfvars              # File cấu hình các biến bảo mật cho Terraform
└── vectorize
    ├── __init__.py
    └── vectorize.py              # Vectorize văn bản sử dụng SentenceTransformer lưu vào Qdrant
```

---

## Mục tiêu học tập và thực tập (Internship Objectives)
1. **Thiết kế hạ tầng dưới dạng mã nguồn (Infrastructure as Code - IaC)**: Sử dụng **Terraform** để định nghĩa và khởi tạo toàn bộ hạ tầng mạng, bảo mật, tính toán và cơ sở dữ liệu trên AWS.
2. **Quản lý và vận hành container (Serverless Containerization)**: Sử dụng Docker để đóng gói các tác vụ xử lý độc lập và chạy serverless bằng **Amazon ECS Fargate** kết hợp với **Amazon ECR**.
3. **Thiết kế mô hình Data Warehouse (Star Schema)**: Áp dụng kiến trúc thiết kế cơ sở dữ liệu quan hệ tối ưu hóa cho phân tích và RAG bằng cách chia tách Dimension Tables và Fact Tables.
4. **Tự động hóa luồng công việc (Workflow Automation)**: Thiết lập lịch trình tự động chạy các tác vụ định kỳ bằng **Amazon EventBridge Scheduler**.
5. **Xây dựng hệ thống RAG (Retrieval-Augmented Generation)**: Thực hành tích hợp cơ sở dữ liệu vector (Vector Database) và gọi API các mô hình ngôn ngữ lớn (LLM) để xây dựng ứng dụng AI hoàn chỉnh.

---

## Kiến trúc hệ thống RAG (RAG Architecture Pipeline)

### 1. Luồng dữ liệu cục bộ (Local Architecture)
* **Thu thập (Ingestion)**: Scrapy Crawler (`crawler/spiders/spider.py`) cào tin tức từ sitemap và đẩy vào Kafka topic `news_raw` (`crawler/pipelines.py`).
* **Lưu trữ thô**: Kafka Consumer (`consumer/consumer.py`) đọc dữ liệu thô và insert vào bảng `article_metadata` trong PostgreSQL.
* **Xử lý kho dữ liệu (ETL)**: ETL process (`etl/etl_warehouse.py`) làm sạch HTML thừa, chia nhỏ văn bản (chunking), và tổ chức lại dữ liệu vào Star Schema (PostgreSQL).
* **Vector hóa (Embedding)**: Vectorizer (`vectorize/vectorize.py`) lấy dữ liệu từ Postgres, chạy model SentenceTransformer cục bộ để sinh vector và lưu lên Qdrant Vector DB.
* **Hỏi đáp (RAG)**: Người dùng truy vấn qua API, hệ thống thực hiện tìm kiếm tương đồng trên Qdrant và tạo prompt sinh câu trả lời thông qua Groq/Gemini API (`search/engine.py`).

### 2. Luồng dữ liệu Cloud v2 (AWS Serverless Architecture)
* **Kích hoạt (Scheduling)**: Amazon EventBridge Scheduler định kỳ kích hoạt ECS Fargate Crawler chạy Sitemap tin tức.
* **Hàng đợi & Consumer**: Crawler đẩy URL/Nội dung vào Amazon SQS. AWS Lambda Consumer tự động trigger khi có message trong queue để lưu dữ liệu thô vào Aurora PostgreSQL.
* **ETL & Embedding**: AWS Lambda ETL đọc dữ liệu, làm sạch, chia nhỏ văn bản thành các chunk. Sau đó gọi API Bedrock Titan Embed (`amazon.titan-embed-text-v2:0`) sinh vector.
* **Aurora PostgreSQL + pgvector**: Vector cùng nội dung chunk và các chiều dữ liệu khác được lưu trữ trực tiếp trên Amazon Aurora Serverless v2 PostgreSQL sử dụng index HNSW.
* **RAG API**: Người dùng truy vấn thông qua Amazon API Gateway. AWS Lambda RAG API nhận request, gọi Bedrock Titan Embed cho câu hỏi, tìm kiếm vector trong Aurora bằng pgvector, rồi gửi thông tin ngữ cảnh đến LLM (Groq/Gemini) để trả lời.

---

## Thiết kế cơ sở dữ liệu quan hệ (Data Warehouse Star Schema)

Cơ sở dữ liệu PostgreSQL được tổ chức theo cấu trúc Star Schema để tối ưu hóa việc tổ chức thông tin và truy vấn (định nghĩa chi tiết tại `database/warehouse.sql`):

* **Dimension Tables**:
  * `dim_source`: Quản lý thông tin các trang báo nguồn (domain).
  * `dim_time`: Quản lý thông tin thời gian xuất bản (ngày, tháng, năm).
  * `dim_content`: Lưu trữ nội dung bài viết đã qua làm sạch.
  * `dim_author`: Quản lý thông tin của các tác giả bài viết.
* **Fact Tables**:
  * `fact_articles`: Bảng sự kiện chính lưu liên kết đến các chiều dữ liệu và thống kê chiều dài nội dung.
  * `fact_article_authors`: Bảng liên kết trung gian thể hiện mối quan hệ nhiều-nhiều giữa bài viết và các tác giả.
  * `fact_chunks`: Lưu trữ các đoạn tin tức sau khi chia tách từ bài viết gốc để phục vụ RAG.

---

## Hạ tầng AWS được quản lý bằng Terraform (`main.tf`)

Mã nguồn Terraform trong dự án triển khai các tài nguyên AWS sau:
1. **Mạng lưới (VPC & Networking)**:
   * Khởi tạo `aws_vpc` riêng biệt (`newsrag-vpc`).
   * Cấu hình các Subnets công khai ở các Availability Zones (ap-southeast-2a, ap-southeast-2b).
   * Tạo Route Table và Internet Gateway cho phép các dịch vụ kết nối mạng.
2. **Bảo mật (Security Groups & IAM Roles)**:
   * IAM Roles phục vụ cho việc thực thi ECS Tasks (`AmazonECSTaskExecutionRolePolicy`).
   * Security Groups kiểm soát luồng giao tiếp mạng giữa ECS Fargate và RDS Database.
3. **Cơ sở dữ liệu (Database)**:
   * Khởi tạo **Amazon Aurora Serverless v2 PostgreSQL** cluster sử dụng cấu hình instance `db.t4g.medium` giúp tối ưu hóa chi phí.
4. **Vận hành & Container (Compute & Registry)**:
   * Tạo **Amazon ECR** repository (`newsrag-api`) để quản lý các Docker Image.
   * Khởi tạo **Amazon ECS Cluster** (`newsrag-cluster`).
   * Định nghĩa 3 ECS Task Definitions chạy Fargate: `crawler`, `etl`, và `vectorize`.
5. **Tự động hóa (Amazon EventBridge Scheduler)**:
   * Định nghĩa lịch chạy định kỳ hàng ngày (cron job) cho từng task nhằm giảm tải tài nguyên hệ thống và tiết kiệm chi phí vận hành:
     * **Crawler Task**: Chạy lúc `01:00 UTC`.
     * **ETL Task**: Chạy lúc `02:00 UTC`.
     * **Vectorize Task**: Chạy lúc `03:00 UTC`.

---

## Hướng dẫn chạy thử nghiệm local (Local Development)

### Yêu cầu hệ thống
* Python 3.10+
* Docker & Docker Compose
* Git

### Các bước cài đặt
1. **Khởi tạo môi trường ảo Python**:
   ```bash
   make setup
   ```
2. **Khởi chạy môi trường giả lập (PostgreSQL, Qdrant, Kafka)**:
   ```bash
   docker compose up -d
   ```
3. **Cài đặt biến môi trường**:
   Sao chép file cấu hình mẫu `.env.example` thành `.env` và điền đầy đủ các thông tin kết nối và API keys:
   ```env
   DB_NAME=newsrag
   DB_USER=postgres
   DB_PASSWORD=yourpassword
   DB_HOST=localhost
   DB_PORT=5432
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   QDRANT_COLLECTION_NAME=news_chunks
   KAFKA_BOOTSTRAP_SERVERS=localhost:9092
   KAFKA_TOPIC_NEWS=news_raw
   GROQ_API_KEY=gsk_...
   GEMINI_API_KEY=AIza...
   ```
4. **Chạy thử nghiệm toàn bộ luồng pipeline cục bộ**:
   * Chạy Crawler để cào dữ liệu và đẩy vào Kafka:
     ```bash
     python main.py --mode crawl
     ```
   * Chạy Consumer để đọc từ Kafka lưu vào Database:
     ```bash
     python consumer/consumer.py
     ```
   * Thực hiện chuẩn hóa ETL:
     ```bash
     python main.py --mode etl
     ```
   * Chuyển đổi dữ liệu và đẩy vào Qdrant Vector DB:
     ```bash
     python main.py --mode vectorize
     ```
   * Kiểm tra giao diện RAG hỏi đáp CLI:
     ```bash
     make test-interactive
     ```

---

## Hướng dẫn triển khai lên AWS (AWS Deployment Guide)

1. **Khởi tạo cơ sở hạ tầng bằng Terraform**:
   ```bash
   aws configure
   terraform init
   terraform apply
   ```
2. **Xây dựng và đẩy Docker image lên Amazon ECR**:
   ```bash
   docker build -t news-crawler .
   aws ecr get-login-password | docker login --username AWS --password-stdin <YOUR_ECR_REPO_URL>
   docker tag news-crawler:latest <YOUR_ECR_REPO_URL>:latest
   docker push <YOUR_ECR_REPO_URL>:latest
   ```
3. **Chạy thủ công các ECS Fargate Tasks (nếu cần)**:
   Bạn có thể kích hoạt các ECS Task trực tiếp thông qua AWS CLI hoặc Console bằng các task definition đã tạo sẵn (`newsrag-crawler`, `newsrag-etl`, `newsrag-vectorize`).
