# Walkthrough: AWS Services Initialization

## Tổng kết các dịch vụ đã khởi tạo

### ✅ Phase 1: IAM Roles & Policies

| Resource | ARN / ID |
|----------|----------|
| Lambda Execution Role | `arn:aws:iam::814808959551:role/newsrag-lambda-execution-role` |
| ECS Execution Role | `arn:aws:iam::814808959551:role/newsrag-ecs-execution-role` |
| ECS Task Role | `arn:aws:iam::814808959551:role/newsrag-ecs-task-role` |
| EventBridge Role | `arn:aws:iam::814808959551:role/newsrag-eventbridge-role` |
| Custom Policy (Bedrock+SQS+CW) | `arn:aws:iam::814808959551:policy/newsrag-custom-policy` |
| ECS Security Group | `sg-0330980a3f9ca4eb0` (đã tồn tại) |
| RDS Security Group | `sg-06481a478ca45da1f` (đã tồn tại, đã allow ECS SG) |

**Policies đã gán cho Lambda Role:**
- `AWSLambdaBasicExecutionRole`
- `AWSLambdaVPCAccessExecutionRole`
- `newsrag-custom-policy` (Bedrock InvokeModel + SQS + CloudWatch)

---

### ✅ Phase 2: SQS Queues

| Queue | URL |
|-------|-----|
| Main Queue | `https://sqs.ap-southeast-2.amazonaws.com/814808959551/newsrag-raw-news` |
| Dead Letter Queue | `https://sqs.ap-southeast-2.amazonaws.com/814808959551/newsrag-raw-news-dlq` |

- VisibilityTimeout: 300s (5 phút)
- MessageRetentionPeriod: 86400s (1 ngày)
- maxReceiveCount: 3 → DLQ

---

### ✅ Phase 4: ECR Repository

| Resource | URI |
|----------|-----|
| ECR Repository | `814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-crawler` |

---

### ✅ Phase 5: ECS Fargate

| Resource | Value |
|----------|-------|
| Cluster | `newsrag-cluster` (ACTIVE) |
| Task Definition | `newsrag-crawler:1` (256 CPU, 512 MB) |
| CloudWatch Log Group | `/ecs/newsrag-crawler` (retention 7 ngày) |

---

### ✅ Phase 8: EventBridge Scheduler

| Rule | Schedule | Target |
|------|----------|--------|
| `newsrag-crawler-schedule` | `cron(0 1 * * ? *)` — 01:00 UTC | ECS Fargate (newsrag-crawler:1) |
| `newsrag-etl-schedule` | `cron(0 2 * * ? *)` — 02:00 UTC | _Pending Lambda ETL_ |

---

### ✅ Phase 9: .env Updated

File [.env](file:///c:/Users/Admin/Desktop/Education/TT/project/NewsRAG/NewsRagProject/.env) đã được cập nhật:

| Section | Thay đổi |
|---------|---------|
| **Qdrant** | ❌ Comment out → ✅ `VECTOR_PROVIDER=pgvector` |
| **Kafka** | ❌ Comment out → ✅ `SQS_QUEUE_URL=...`, `SQS_REGION=ap-southeast-2` |
| **Bedrock** | ❌ `api_key` mode → ✅ `auto` mode (IAM role) |

---

## 🔲 Công việc còn lại

> [!IMPORTANT]
> Các phase dưới đây cần **code thay đổi** (viết Lambda handler) hoặc **quyền truy cập database** (pgvector). Đây là phần của từng thành viên team.

### Phase 3: pgvector Extension
Bạn cần kết nối psql vào Aurora và chạy:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Phase 6: Lambda Functions
Cần viết code cho 3 Lambda handlers:
- **Consumer**: Nhận SQS → insert Aurora (thay thế Kafka consumer)
- **ETL**: Clean + Chunk + Bedrock Embed → insert pgvector
- **RAG API**: Query → Embed → pgvector search → LLM

### Phase 7: API Gateway
Tạo REST API endpoint cho RAG API Lambda.

---

## AWS Policy Files

Tất cả policy/config files được lưu tại [aws-policies/](file:///c:/Users/Admin/Desktop/Education/TT/project/NewsRAG/NewsRagProject/aws-policies/):
- `lambda-trust-policy.json`
- `ecs-trust-policy.json`
- `newsrag-custom-policy.json`
- `eventbridge-trust-policy.json`
- `eventbridge-policy.json`
- `ecs-task-definition.json`
- `eventbridge-crawler-target.json`
- `sqs-dlq-attributes.json`
- `sqs-main-attributes.json`

> [!TIP]
> Thêm `aws-policies/` vào `.gitignore` nếu không muốn commit các file này (chứa account-specific ARNs).
