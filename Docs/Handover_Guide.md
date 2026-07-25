

## 1. Tổng quan Kiến trúc Hệ thống (Architecture)
Hệ thống NewsRAG là một pipeline thu thập và xử lý dữ liệu báo chí hoàn toàn trên AWS (Serverless & Managed Services), bao gồm các thành phần chính:

1. **Crawler (AWS ECS Fargate)**: Chạy định kỳ thông qua EventBridge, sử dụng Scrapy (SitemapSpider) để thu thập tin tức từ các trang báo và đẩy thông điệp (messages) vào SQS. Fargate được chọn thay cho Lambda vì Lambda bị giới hạn 15 phút timeout (không đủ để cào dữ liệu qua sitemap).
2. **Message Queue (AWS SQS)**: `newsrag-etl-queue` làm bộ đệm chứa các link bài viết cần xử lý, giúp hệ thống không bị quá tải.
3. **ETL & Vectorize (AWS Lambda)**: Nhận message từ SQS, tải nội dung bài báo, cắt đoạn (chunking), gọi **AWS Bedrock (`cohere.embed-multilingual-v3`)** để tạo vector embeddings và lưu vào Datawarehouse.
4. **Datawarehouse (AWS RDS Aurora PostgreSQL)**: Cài đặt extension `pgvector`. Lưu trữ meta-data bài báo (`fact_articles`, `article_metadata`) và vector (`fact_vectors`, `fact_chunks`).
5. **Frontend Dashboard (Next.js)**: Nơi người dùng tìm kiếm ngữ nghĩa (Semantic Search), xem trạng thái pipeline và duyệt bài báo.

---

## 2. Cách Chạy và Phát triển Frontend Cục bộ (Local)

Toàn bộ ứng dụng giao diện nằm trong thư mục `frontend/`. Frontend kết nối trực tiếp với Database RDS và gọi API AWS Bedrock để xử lý Semantic Search.

**Bước 1: Cấu hình biến môi trường (`.env`)**
Bạn cần đảm bảo file `.env` ở **thư mục gốc** (`NewsRagProject/.env`) chứa đầy đủ các thông tin:
- Chìa khóa AWS (`2_ACCESS_KEY_ID`, `2_SECRET_ACCESS_KEY`, `2_REGION`) cho Bedrock và CloudWatch.
- Mẫu model Bedrock (`BEDROCK_EMBEDDING_MODEL_ID=cohere.embed-multilingual-v3`).
- Thông tin DB RDS (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).

**Bước 2: Chạy Frontend**
```bash
cd frontend
npm install
npm run dev
```
Truy cập `http://localhost:3000/dashboard/search` để bắt đầu trải nghiệm hệ thống tìm kiếm tin tức bằng AI.

---

## 3. Cách Kiểm tra và Theo dõi Dịch vụ trên AWS (Monitoring)

Tất cả các dịch vụ đều đang chạy trên AWS. Để theo dõi "sức khỏe" của dự án, hãy đăng nhập vào **AWS Console** và kiểm tra các mục sau:

### 3.1. AWS CloudWatch (Giám sát Tổng thể)
Đây là trung tâm kiểm soát chính của dự án.
- **Dashboard**: Tìm đến mục *CloudWatch > Dashboards > `NewsRAG-Dashboard`*. Tại đây bạn có thể thấy các biểu đồ về số lượng tin nhắn trong hàng đợi SQS, thời gian thực thi của Lambda và tỷ lệ lỗi (Error Rates).
- **Log Groups**: Để xem log chi tiết của quá trình Crawl (trên Fargate) hoặc xử lý lỗi của ETL (trên Lambda):
  - `/ecs/newsrag-crawler`: Chứa log của các container Fargate (Quá trình thu thập tin tức từ sitemap).
  - `/aws/lambda/newsrag-etl`: Chứa log của quá trình chunking, embedding qua Bedrock và ghi vào database bằng Lambda.

### 3.2. AWS SQS (Hàng đợi)
- Truy cập *Simple Queue Service (SQS)* > chọn `newsrag-etl-queue`.
- Kiểm tra thông số **Messages available** để biết số lượng bài báo đang chờ xử lý. Nếu số lượng này tăng liên tục mà không giảm, có thể Lambda ETL đang gặp lỗi và bạn cần check log CloudWatch.

### 3.3. AWS Bedrock (Mô hình AI)
- Truy cập *Amazon Bedrock > Model access*. 
- Dự án sử dụng mô hình **Cohere Embed Multilingual v3**. Hãy đảm bảo trạng thái truy cập (Access status) của mô hình này đang là "Access granted" trong Region của bạn (hiện đang dùng `ap-southeast-1` hoặc `ap-southeast-2` tùy cấu hình).

### 3.4. AWS RDS (Cơ sở dữ liệu)
- Dự án dùng **Aurora PostgreSQL**.
- Bạn có thể kết nối vào RDS thông qua các công cụ như DBeaver, DataGrip hoặc `psql` bằng thông tin trong file `.env` để kiểm tra trực tiếp dữ liệu ở bảng `fact_articles` và `fact_chunks`.

