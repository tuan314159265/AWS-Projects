# Tài liệu Tổng hợp Kiến trúc NewsRAG trên AWS & Kịch bản Demo

Dự án NewsRAG hiện đã được chuyển đổi hoàn toàn từ kiến trúc chạy cục bộ (Local) sang kiến trúc không máy chủ (Serverless) trên AWS. Tài liệu này tóm tắt lại các thành phần đã triển khai và cung cấp kịch bản chạy thử nghiệm (demo) từ đầu đến cuối.

---

## Phần 1: Tóm tắt Kiến trúc Hệ thống trên AWS

Hệ thống hiện tại bao gồm 4 thành phần chính hoạt động liên kết với nhau trên nền tảng đám mây AWS:

### 1. Cơ sở dữ liệu (Database & Vector Store)
- **Dịch vụ:** Amazon Aurora PostgreSQL (Serverless v2).
- **Vai trò:** Lưu trữ toàn bộ bài viết tin tức thô và cấu hình mở rộng `pgvector` để lưu trữ vector nhúng (embeddings) cho RAG.
- **Bảo mật:** Chạy trong mạng riêng ảo (VPC), chỉ cho phép truy cập từ các dịch vụ AWS nội bộ (Lambda, ECS).

### 2. Trình thu thập tin tức (News Crawler)
- **Dịch vụ:** Amazon ECS (Fargate) & Amazon ECR (`newsrag-crawler`).
- **Vai trò:** Là một container chạy theo tác vụ (Task). Khi được kích hoạt, nó sẽ cào các tin tức mới nhất từ các trang báo, sau đó đẩy dữ liệu thô này vào CSDL và gửi thông báo qua hàng đợi SQS.

### 3. Luồng xử lý dữ liệu (ETL Pipeline)
- **Dịch vụ:** AWS Lambda (`newsrag-etl`) & Amazon EventBridge.
- **Vai trò:** Chạy định kỳ (hoặc kích hoạt thủ công) để lấy dữ liệu thô, tiến hành làm sạch, chia nhỏ (chunking) văn bản và gọi **Amazon Bedrock (Titan Embeddings)** để tạo vector, cuối cùng lưu vào bảng pgvector.
- **Trigger:** EventBridge tự động gọi hàm Lambda này vào một khung giờ cố định mỗi ngày.

### 4. Giao diện Chatbot & Truy vấn (RAG API)
- **Dịch vụ:** API Gateway & AWS Lambda (`newsrag-rag-api`).
- **Vai trò:** Tiếp nhận câu hỏi của người dùng qua HTTP POST (`/query`). 
- **Quy trình:**
  1. Tạo vector cho câu hỏi (qua Bedrock).
  2. Truy vấn tìm kiếm ngữ nghĩa (Semantic Search) trong Aurora pgvector để tìm các bài báo liên quan nhất.
  3. Đưa nội dung tìm được vào LLM (Claude 3.5 Sonnet qua Bedrock hoặc Qwen3 qua Groq) để tạo câu trả lời tự nhiên.
- **Endpoint Public:** `https://2ohkfkehda.execute-api.ap-southeast-2.amazonaws.com/prod/query`

---

## Phần 2: Kịch bản Demo (Hướng dẫn chạy từng bước)

Dưới đây là kịch bản để bạn tự tay chạy thử toàn bộ luồng dữ liệu của dự án NewsRAG từ lúc cào tin đến lúc trả lời câu hỏi.

### Bước 1: Khởi động Crawler để lấy dữ liệu
Bạn cần kích hoạt file cấu hình ECS Task để Crawler bắt đầu cào báo.

1. Đăng nhập vào **AWS Management Console**.
2. Tìm và mở dịch vụ **Amazon ECS**.
3. Vào phần **Task definitions**, chọn `newsrag-crawler`.
4. Click nút **Run new task** (hoặc Deploy). 
5. Chọn **Fargate**, chọn VPC và Subnet mặc định của dự án (`subnet-048dc1f4e2d6bd465`, `subnet-0d8c1471aa391915b`), chọn Security Group `sg-0330980a3f9ca4eb0`.
6. Bấm **Run Task**.
7. *Chờ khoảng 1-2 phút cho task chạy xong. Lúc này trong DB đã có các bản tin thô (raw data).*

> [!TIP]
> **Cách test không cần AWS (Test nhanh tại Local):** 
> Nếu không muốn chạy ECS, bạn có thể chạy file `main.py --mode crawl` trực tiếp trên máy của bạn (vì máy bạn đang được phép kết nối đến DB RDS).

### Bước 2: Chạy ETL Pipeline để tạo Vector (Embeddings)
Sau khi đã có tin tức thô, ta cần mã hóa chúng thành Vector.

1. Mở dịch vụ **AWS Lambda** trên AWS Console.
2. Chọn hàm `newsrag-etl`.
3. Chuyển sang tab **Test**.
4. Tạo một sự kiện test mới (chỉ cần để JSON rỗng `{}`) và bấm **Test**.
5. *Hàm Lambda sẽ chạy (mất khoảng 10-30 giây tùy lượng tin). Khi thành công, nó sẽ trả về kết quả JSON kiểu như: `{"etl_processed": 50, "vectors_created": 50}`.*

> [!NOTE]
> Trong môi trường thực tế, bước này tự động chạy hàng ngày nhờ EventBridge, bạn không cần bấm Test thủ công.

### Bước 3: Đặt câu hỏi qua RAG API (Thành quả)
Cuối cùng, khi dữ liệu đã được nạp và Vector hóa thành công, bạn có thể thử hỏi Chatbot.

1. Mở terminal (CMD/PowerShell) trên máy bạn.
2. Chạy lệnh sau để gửi câu hỏi đến hệ thống:

```powershell
curl -X POST "https://2ohkfkehda.execute-api.ap-southeast-2.amazonaws.com/prod/query" ^
     -H "Content-Type: application/json" ^
     -d "{\"query\": \"Tóm tắt những tin tức nổi bật mới nhất hôm nay ở Việt Nam\"}"
```

> [!TIP]
> **Nếu dùng Postman:**
> - Method: `POST`
> - URL: `https://2ohkfkehda.execute-api.ap-southeast-2.amazonaws.com/prod/query`
> - Body -> raw -> JSON:
>   ```json
>   {
>     "query": "Tóm tắt những tin tức nổi bật mới nhất hôm nay ở Việt Nam"
>   }
>   ```

3. **Kết quả trả về** sẽ là một đoạn JSON bao gồm:
   - `summary`: Câu trả lời được tổng hợp bằng AI (Claude Sonnet / Qwen3).
   - `results`: Danh sách các bài báo gốc mà AI đã đọc để lấy thông tin trả lời.

---
**Chúc mừng!** Tới bước này bạn đã hoàn tất luồng demo toàn diện của hệ thống NewsRAG phiên bản Serverless trên AWS.
