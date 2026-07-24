# News RAG Pipeline on AWS — v2

# Bỏ terraform config thủ công trên AWS

## Giới thiệu

News RAG là hệ thống **tổng hợp và phân tích tin tức thông minh**, ứng dụng kiến trúc RAG (Retrieval-Augmented Generation) để tự động thu thập tin tức từ các báo điện tử Việt Nam, xử lý và lưu trữ dữ liệu theo mô hình Star Schema, tạo embedding vector qua **Amazon Bedrock**, và cho phép người dùng đặt câu hỏi bằng ngôn ngữ tự nhiên — hệ thống sẽ truy xuất các đoạn tin tức liên quan và tổng hợp câu trả lời thông qua các mô hình ngôn ngữ lớn (LLM) như Groq Qwen3, Gemini Flash.

### Mục tiêu

1. Xây dựng pipeline tự động crawl tin tức từ nhiều nguồn báo
2. Chuẩn hóa dữ liệu theo mô hình Data Warehouse (Star Schema)
3. Tạo embedding vector và lưu trữ trong cơ sở dữ liệu vector
4. Xây dựng hệ thống RAG cho phép hỏi đáp thông minh dựa trên tin tức
5. Triển khai hoàn toàn trên AWS với kiến trúc serverless, tối ưu chi phí

---

## Kiến trúc tổng thể — v2

```text
EventBridge Scheduler (01:00, 02:00 UTC)
       │
       ├──[01:00]──► Fargate Crawler ──► SQS ──► Lambda Consumer
       │               (Scrapy Sitemap)            (SHA256 + insert Aurora)
       │
       └──[02:00]──► Lambda ETL
                       (clean → chunk → Bedrock Embed → insert Aurora pgvector)

                              ▲
                              │ top-k chunks
                     Lambda RAG API ◄── API Gateway ◄── Client
                     (Bedrock Embed query → pgvector search → Groq/Gemini LLM)
```

---

## So sánh kiến trúc v1 và v2

| Component           | v1 (Khóa luận)                                                | v2 (Cải tiến)                                  | Lý do                                                         |
| ------------------- | ------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| **Crawler**         | Lambda + Scrapy (`DEPTH_LIMIT`, 15 phút timeout)              | **Fargate + SitemapSpider**                    | Không bị timeout, crawl được bài cũ qua sitemap XML           |
| **Stream**          | Kafka trên Docker                                             | **SQS Standard (~$0)**                         | Overkill cho pipeline nhỏ, Kafka tốn chi phí quản lý          |
| **Embedding**       | `BAAI/bge-m3` local (1024d, 568M params) → `BGE-small` (384d) | **`amazon.titan-embed-text-v2` (Bedrock API)** | 100% AWS native, không tải model, serverless, giảm cold start |
| **Vector DB**       | Qdrant Cloud (dịch vụ bên thứ ba)                             | **Aurora PostgreSQL + pgvector**               | Tận dụng RDS sẵn có, không phụ thuộc bên ngoài                |
| **Vectorize**       | Fargate riêng biệt (tốn ~$3/tháng)                            | **Gộp vào Lambda ETL**                         | Giảm 1 dịch vụ, đơn giản hóa pipeline                         |
| **RAG query embed** | Load model local (cold start 5–10 giây)                       | **Gọi Bedrock API**                            | Nhất quán vector space, không load model                      |
| **Frontend**        | Next.js + FastAPI                                             | **Giữ nguyên**                                 | Không thay đổi                                                |
| **Tổng chi phí**    | **~$35/tháng**                                                | **~$21–26/tháng**                              | Giảm ~30%                                                     |

> **Quan trọng:** ETL và RAG API dùng **cùng một embedding model** (`amazon.titan-embed-text-v2:0`). Khác model → vector space lệch → kết quả tìm kiếm sai.

---

## Component map

| Module          | Công nghệ                                   | Ghi chú                                                        |
| --------------- | ------------------------------------------- | -------------------------------------------------------------- |
| **Crawler**     | ECS Fargate + Scrapy SitemapSpider          | Crawl sitemap_news.xml, chạy ~30 phút/ngày, 1 vCPU 2GB RAM     |
| **Queue**       | SQS Standard                                | Thay Kafka, ~$0/tháng                                          |
| **Consumer**    | Lambda (trigger SQS)                        | SHA256 dedup URL, insert raw article vào Aurora                |
| **ETL + Embed** | Lambda (15 phút timeout)                    | Clean HTML → chunk 500 token → Bedrock embed → insert pgvector |
| **Embedding**   | Amazon Bedrock `titan-embed-text-v2:0`      | 1024 chiều, dùng chung cho ETL và RAG query                    |
| **Warehouse**   | Aurora Serverless v2 + pgvector             | PostgreSQL + vector search HNSW, 2 ACU (~4GB RAM)              |
| **RAG API**     | Lambda + API Gateway                        | Embed query → pgvector search → gọi LLM                        |
| **LLM**         | Groq (Qwen3-8B) + Gemini 2.0 Flash fallback | External API, không chạy local                                 |
| **Schedule**    | EventBridge Scheduler                       | 2 ca/ngày (01h, 02h UTC)                                       |
| **Frontend**    | Next.js + Tailwind CSS + FastAPI            | Dashboard, Search, Chat, Explorer, Pipeline Monitor            |

---

## Chi tiết kỹ thuật

### 1. Fargate Crawler

Sử dụng `SitemapSpider` của Scrapy để crawl qua sitemap XML. Khác với `CrawlSpider` (dùng `DEPTH_LIMIT`, bỏ sót bài cũ), SitemapSpider đọc toàn bộ URL từ sitemap, không phụ thuộc navigation.

**Sitemap URLs thực tế:**

| Báo        | URL                                      |
| ---------- | ---------------------------------------- |
| VnExpress  | `https://vnexpress.net/sitemap_news.xml` |
| Thanh Niên | `https://thanhnien.vn/sitemap.xml`       |
| VietnamNet | `https://vietnamnet.vn/sitemap_news.xml` |

```python
import scrapy
from scrapy.spiders import SitemapSpider

class NewsSitemapSpider(SitemapSpider):
    name = "news_sitemap"
    sitemap_urls = [
        "https://vnexpress.net/sitemap_news.xml",
        "https://thanhnien.vn/sitemap.xml",
        "https://vietnamnet.vn/sitemap_news.xml",
    ]
    sitemap_rules = [("/", "parse_article")]
    custom_settings = {
        "DOWNLOAD_DELAY": 1, "CONCURRENT_REQUESTS": 8, "ROBOTSTXT_OBEY": True,
    }

    def parse_article(self, response):
        yield {
            "url": response.url,
            "title": response.css("h1::text").get(),
            "content": " ".join(response.css("article p::text").getall()),
            "published_at": response.css("time::attr(datetime)").get(),
            "author": response.css(".author-name::text, .author::text").get(),
        }
```

### 2. Lambda Consumer

Nhận message từ SQS, hash URL bằng SHA256 để tránh trùng lặp, insert bài thô vào Aurora.

```python
import hashlib, json, psycopg2, os

def handler(event, context):
    conn = psycopg2.connect(os.environ["AURORA_DSN"])
    cur = conn.cursor()
    for record in event["Records"]:
        article = json.loads(record["body"])
        url_hash = hashlib.sha256(article["url"].encode()).hexdigest()
        cur.execute("""
            INSERT INTO articles (url_hash, url, title, content, published_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (url_hash) DO NOTHING
        """, (url_hash, article["url"], article["title"],
              article["content"], article["published_at"]))
    conn.commit()
```

### 3. Lambda ETL + Bedrock Embed

Clean HTML, chunk ~500 token (overlap 50), gọi Bedrock Titan Embed để lấy vector 1024 chiều, insert vào Aurora pgvector.

```python
import boto3, json, psycopg2, os, re

bedrock = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])

def embed(text: str) -> list[float]:
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text})
    )
    return json.loads(resp["body"].read())["embedding"]

def chunk(text: str, size=500, overlap=50) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunks.append(" ".join(words[i:i + size]))
    return chunks

def clean_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def handler(event, context):
    conn = psycopg2.connect(os.environ["AURORA_DSN"])
    cur = conn.cursor()
    cur.execute("SELECT id, content FROM articles WHERE embedded = false LIMIT 50")
    for article_id, content in cur.fetchall():
        cleaned = clean_html(content)
        for i, chunk_text in enumerate(chunk(cleaned)):
            vector = embed(chunk_text)
            cur.execute("""
                INSERT INTO article_chunks (article_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s)
            """, (article_id, i, chunk_text, vector))
        cur.execute("UPDATE articles SET embedded = true WHERE id = %s", (article_id,))
    conn.commit()
```

### 4. Aurora pgvector — Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE articles (
    id          SERIAL PRIMARY KEY,
    url_hash    TEXT UNIQUE NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT,
    content     TEXT,
    published_at TIMESTAMPTZ,
    embedded    BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE article_chunks (
    id          SERIAL PRIMARY KEY,
    article_id  INTEGER REFERENCES articles(id),
    chunk_index INTEGER,
    content     TEXT,
    embedding   vector(1024)  -- Titan Embed v2 output: 1024 chiều
);

-- HNSW index cho similarity search
CREATE INDEX ON article_chunks
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

### 5. Lambda RAG API

```python
import boto3, json, psycopg2, os, requests

bedrock = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

def embed_query(query: str) -> list[float]:
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": query})
    )
    return json.loads(resp["body"].read())["embedding"]

def retrieve(query_vec: list[float], top_k=5):
    conn = psycopg2.connect(os.environ["AURORA_DSN"])
    cur = conn.cursor()
    cur.execute("SET hnsw.ef_search = 40")
    cur.execute("""
        SELECT content, title FROM article_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_vec, top_k))
    return cur.fetchall()

def call_llm(messages, model="qwen/qwen3-8b-instant"):
    resp = requests.post(
        GROQ_API,
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={"model": model, "messages": messages},
        timeout=30
    )
    return resp.json()["choices"][0]["message"]["content"]

def handler(event, context):
    body = json.loads(event["body"])
    query = body["query"]
    query_vec = embed_query(query)
    chunks = retrieve(query_vec, top_k=5)
    context_text = "\n\n".join([c[0] for c in chunks])

    try:
        answer = call_llm([
            {"role": "system", "content": "Trả lời bằng tiếng Việt, dựa trên ngữ cảnh tin tức sau."},
            {"role": "user", "content": f"Ngữ cảnh:\n{context_text}\n\nCâu hỏi: {query}"}
        ])
    except Exception:
        answer = call_llm([
            {"role": "system", "content": "Trả lời bằng tiếng Việt, dựa trên ngữ cảnh tin tức sau."},
            {"role": "user", "content": f"Ngữ cảnh:\n{context_text}\n\nCâu hỏi: {query}"}
        ], model="gemini-2.0-flash")

    return {"statusCode": 200, "body": json.dumps({"answer": answer, "sources": chunks})}
```

---

## Chi phí vận hành

| Nhóm              | Component                                                            | Giá/tháng         |
| ----------------- | -------------------------------------------------------------------- | ----------------- |
| **Crawl + Queue** | Fargate Crawler (1 vCPU, 2GB, ~30 phút/ngày) + SQS + Lambda Consumer | **~$3–5**         |
| **ETL + Embed**   | Lambda ETL + Bedrock Titan Embed (~5000 bài/ngày × ~30 chunk/bài)    | **~$1–3**         |
| **Database**      | Aurora Serverless v2 (2 ACU) + pgvector                              | **~$14**          |
| **RAG API**       | Lambda RAG API + API Gateway                                         | **~$3–4**         |
| **Tổng**          |                                                                      | **~$21–26/tháng** |

---

## Kết quả đánh giá

### Chỉ số Ragas

Hệ thống được đánh giá bằng framework Ragas với 4 chỉ số:

| Chỉ số                | Ý nghĩa                                           | Nhận xét                                |
| --------------------- | ------------------------------------------------- | --------------------------------------- |
| **Faithfulness**      | Mức độ trung thực của câu trả lời so với ngữ cảnh | Cải thiện khi Context Recall tăng       |
| **Answer Relevancy**  | Mức độ liên quan của câu trả lời với câu hỏi      | Ngưỡng khiêm tốn do LLM trả lời lan man |
| **Context Precision** | Khả năng xếp hạng tài liệu liên quan lên đầu      | **NewsRAG vượt trội** so với FlashRAG   |
| **Context Recall**    | Khả năng lấy đủ tài liệu liên quan                | **FlashRAG ổn định hơn**                |

> **Lưu ý:** Tổng thể các chỉ số đều ở mức khiêm tốn (dưới 0.5), điều này **không phản ánh việc hệ thống trả lời sai**. Khung đánh giá Ragas sử dụng LLM để dịch ngược câu trả lời thành câu hỏi ban đầu; do các hệ thống RAG thường được cấu hình prompt để trả lời chi tiết, diễn giải đầy đủ bối cảnh thay vì trả lời cộc lốc, sự lan man này đã làm giảm độ tương đồng cosine với câu hỏi gốc.

### So sánh NewsRAG vs FlashRAG

| Tiêu chí          | FlashRAG                           | NewsRAG                                 |
| ----------------- | ---------------------------------- | --------------------------------------- |
| Context Precision | Trung bình                         | **Cao hơn** (xếp hạng tài liệu tốt hơn) |
| Context Recall    | **Cao hơn** (lấy đủ thông tin hơn) | Trung bình                              |
| Faithfulness      | **Cao hơn** (nhờ Recall tốt)       | Trung bình                              |
| Answer Relevancy  | Tương đương                        | Tương đương                             |
| Prompt tối ưu     | Mặc định                           | **Đi thẳng vào trọng tâm**              |

### Hướng cải thiện

Để nâng cao chất lượng, luồng truy xuất cần được cấu hình lại để cải thiện **Context Recall**, từ đó kéo theo sự cải thiện của **Faithfulness**. Các hướng cụ thể:

- Thử nghiệm chunking theo ngữ nghĩa thay vì chunking cố định
- Mở rộng bộ lọc metadata (theo thời gian, nguồn tin)
- Tinh chỉnh chiến lược truy xuất (top-K động, hybrid search)

---

## Giao diện hệ thống

Giao diện được xây dựng bằng **Next.js + React + Tailwind CSS**, backend FastAPI.

### 1. Dashboard — Bảng điều khiển

Trực quan hóa các chỉ số quan trọng:

- Tổng khối lượng bài báo
- Tổng số vector chunks đã xử lý
- Sự đa dạng của nguồn tin
- Biểu đồ phân tích xu hướng thu thập dữ liệu theo thời gian
- Tỷ trọng phân bổ dữ liệu giữa các nguồn báo
- Bảng xếp hạng các tác giả phổ biến

### 2. Search Page — Tìm kiếm bài báo

- Thanh tìm kiếm chính
- Bộ lọc theo nguồn báo, khoảng thời gian, số lượng kết quả
- Kết quả hiển thị: tiêu đề, nguồn tin, ngày xuất bản, đoạn trích nội dung, liên kết bài gốc
- Sắp xếp theo thời gian

### 3. AI Chat — Trò chuyện với AI

- Tương tác với nhiều model AI (Qwen, Gemini Flash...)
- So sánh câu trả lời giữa các model
- Trích dẫn nguồn tin tức trong câu trả lời

### 4. Article Explorer — Kiểm soát danh sách vector

- Duyệt dữ liệu bài báo đã xử lý
- Xem chi tiết quá trình chunking
- Thông tin: thứ tự chunk, số lượng token ước tính

### 5. Pipeline Monitor

- Trạng thái kết nối của các thành phần (Database, Vector DB, Kafka, LLM)
- Trực quan hóa luồng xử lý: crawling → streaming → ETL → vector ingestion
- Nhật ký hệ thống theo thời gian thực

---

## IAM Policy cho Lambda

```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
}
```

Ngoài ra cần thêm: `AmazonSQSReadOnlyAccess`, `SecretsManagerReadWrite`, và policy cho CloudWatch Logs.

---

## Phân chia công việc

| Thành viên | Module              | AWS Services                                           | Công việc chính                                                                                                                                         |
| ---------- | ------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trọng**  | Crawl + Queue       | ECS Fargate, SQS, ECR, Docker                          | Dockerfile cho Fargate Crawler, cấu hình SQS + Dead Letter Queue, deploy Docker image lên ECR, viết Sitemap Spider cho Scrapy crawl 3 báo               |
| **Tiến**   | Consumer + Database | Lambda, Aurora, pgvector, Secrets Manager              | Lambda Consumer (trigger SQS), tạo Aurora cluster + pgvector, viết init schema SQL (articles + article_chunks + HNSW index), quản lý connection pooling |
| **Tuấn**   | ETL + Embedding     | Lambda, Bedrock, S3 (artifact)                         | Lambda ETL: clean HTML, chunk text, gọi Bedrock Titan Embed, insert vector vào Aurora. Xử lý retry khi Bedrock rate limit                               |
| **Ly**     | RAG API + Frontend  | Lambda, API Gateway, Groq/Gemini API, Next.js, FastAPI | Lambda RAG: embed query → search pgvector → gọi LLM. API Gateway REST endpoint, CORS + error handling. Frontend: Dashboard, Search, Chat, Explorer      |

### Timeline 4 tuần

| Tuần  | Trọng                             | Tiến                                    | Tuấn                                      | Ly                                    |
| ----- | --------------------------------- | --------------------------------------- | ----------------------------------------- | ------------------------------------- |
| **1** | Dockerfile, SQS queue, deploy ECR | Lambda Consumer, init Aurora + pgvector | Lambda ETL: clean + chunk + Bedrock embed | Lambda RAG: embed + pgvector search   |
| **2** | Sitemap spider, test crawl → SQS  | Test Consumer → Aurora, HNSW index      | ETL full flow, batch processing           | API Gateway + Frontend: Chat page     |
| **3** | EventBridge schedule, DLQ config  | Monitoring, CloudWatch                  | Retry logic, error handling               | Frontend: Dashboard, Search, Explorer |
| **4** | Terraform + CI/CD                 | Terraform + CI/CD                       | Terraform + CI/CD                         | Terraform + CI/CD, integration test   |

---

## Hướng phát triển

### Cải thiện chất lượng truy xuất

- Thử nghiệm chunking theo ngữ nghĩa
- Mở rộng bộ lọc metadata (thời gian, nguồn tin)
- Tinh chỉnh reranker cho miền tin tức tiếng Việt
- Xây dựng bộ dữ liệu đánh giá đa dạng hơn

### Tối ưu mô hình sinh

- Tối ưu prompt, bổ sung cơ chế trích dẫn nguồn
- Kết hợp mô hình chuyên biệt cho từng tác vụ (tóm tắt, hỏi đáp, phân loại)
- Đánh giá bán tự động với phản hồi người dùng

### Mở rộng sản phẩm

- Bổ sung cảnh báo theo chủ đề (topic alert)
- Tóm tắt xu hướng theo thời gian
- So sánh góc nhìn giữa các nguồn báo
- Hỗ trợ cập nhật dữ liệu gần thời gian thực

---

## Deploy

```bash
# 1. Cấu hình AWS
aws configure

# 2. Deploy infrastructure
terraform init #
terraform apply

# 3. Build và push Docker image Fargate Crawler
docker build -t news-crawler ./crawler
aws ecr get-login-password | docker login --username AWS --password-stdin <ECR_URI>
docker tag news-crawler:latest <ECR_URI>/news-crawler:latest
docker push <ECR_URI>/news-crawler:latest

# 4. Deploy Lambda functions
./deploy.sh
```

## Phát triển local

```bash
# 1. Setup môi trường Python
make setup

# 2. Chạy Postgres local với pgvector
docker compose up -d postgres

# 3. Test crawler
cd crawler && scrapy crawl news_sitemap -o output.json

# 4. Test RAG API
make test-interactive
```

## Biến môi trường

Copy `.env.example` → `.env` và điền:

```env
AURORA_DSN=postgresql://user:pass@host:5432/newsdb
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
AWS_REGION=us-east-1
```

> Bedrock không cần API key — dùng IAM role của Lambda với policy `bedrock:InvokeModel`.
