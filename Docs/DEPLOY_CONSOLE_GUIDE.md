# Hướng dẫn deploy bằng tay trên AWS Console

> Làm theo thứ tự từ trên xuống, không skip bước.

---

## I. BUILD TRƯỚC (trên máy local)

### 1. Build frontend

```bash
cd ~/AWS-Project/frontend

# Set API_URL trỏ vào ALB (sau khi có ALB sẽ update lại)
VITE_API_URL=http://localhost:8000 npm install
VITE_API_URL=http://localhost:8000 npm run build

# Sau build sẽ có thư mục dist/
ls dist/
# index.html  assets/
```

### 2. Build Docker image cho backend

```bash
cd ~/AWS-Project

# Build image cho API server
docker build -t newsrag-api .
```

---

## II. BACKEND — TẠM LƯU LOCAL

Frontend build xong + Docker image xong thì chuyển qua web.

---

## III. AWS CONSOLE — BACKEND

Mở https://console.aws.amazon.com , login account `814808959551`.

### A. Tạo Security Group cho ALB


### B. Tạo Target Group

1. Vào **EC2 → Target Groups → Create target group**
2. Chọn:
   - Target type: `IP addresses`
   - Protocol: `HTTP`
   - Port: `8000`
   - VPC: `newsrag-vpc`
   - Health check path: `/health`
   - **Next**
3. **Create** (không cần register target — ECS tự đăng ký)

### C. Tạo ALB (Application Load Balancer)

1. Vào **EC2 → Load Balancers → Create Load Balancer → Application Load Balancer**
2. Config:
   - Name: `newsrag-api-alb`
   - Scheme: `Internet-facing`
   - IP type: `ipv4`
   - VPC: `newsrag-vpc`
   - **Mappings**: chọn cả 2 subnets (`ap-southeast-2a`, `ap-southeast-2b`)
   - Security group: chọn `newsrag-alb-sg` (bỏ default)
   - Listener: HTTP:80, forward to `newsrag-api-tg`
   - **Create load balancer**
3. Sau khi tạo xong, copy DNS name (vd: `newsrag-api-alb-xxxxxx.ap-southeast-2.elb.amazonaws.com`) newsrag-api-alb-1335688100.ap-southeast-2.elb.amazonaws.com

### D. Push Docker image lên ECR

1. Vào **ECR → Repositories → newsrag-api**
2. Click **View push commands**
3. Copy 4 lệnh ở tab "Mac/Linux" và chạy từng cái trên máy local (thay `aws_account_id` = `814808959551`):

```bash
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com
docker tag newsrag-api:latest 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-api:latest
docker push 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-api:latest
```

> Nếu chưa cài AWS CLI thì thôi, có thể dùng cách khác.

### E. Tạo ECS Task Definition cho API

1. Vào **ECS → Task Definitions → Create new task definition**
2. Config:
   - Family: `newsrag-api`
   - Launch type: `FARGATE`
   - Task CPU: `0.5 vCPU`
   - Task Memory: `1 GB`
   - Task role: `newsrag-ecs-task-role`
   - Task execution role: `newsrag-ecs-execution-role`
   - **Next**
3. **Container**:
   - Name: `api`
   - Image URI: `814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-api:latest`
   - Port mappings: `8000` TCP
   - **Command override**: `python,-m,uvicorn,app.api:app,--host,0.0.0.0,--port,8000`
   - **Environment variables** — thêm từng cái:

| Key | Value |
|-----|-------|
| DB_HOST | `newsrag-instance-1.cn8uwuau2s7x.ap-southeast-2.rds.amazonaws.com` |
| DB_PORT | `5432` |
| DB_NAME | `postgres` |
| DB_USER | `newsrag_admin` |
| DB_PASSWORD | `newsrag_admin` |
| VECTOR_HOST | `1dbe8b30-05be-452b-8ae6-bd3d0d18464c.us-west-2-0.aws.cloud.qdrant.io` |
| VECTOR_PORT | `6333` |
| VECTOR_API_KEY | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (full key từ .env) |
| VECTOR_COLLECTION | `news_chunks` |
| BEDROCK_AUTH_MODE | `api_key` |
| BEDROCK_API_KEY | `ABSKQmVkcm9ja0FQSUtleS01MjJ5LWF0...` (full key từ .env) |
| BEDROCK_REGION | `ap-southeast-1` |
| EMBEDDING_PROVIDER | `bedrock` |
| EMBEDDING_MODEL_ID | `amazon.titan-embed-text-v2:0` |
| EMBEDDING_DIMENSION | `1024` |
| LLM_COUNT | `3` |
| LLM_1_NAME | `gpt-oss-120b` |
| LLM_1_PROVIDER | `groq` |
| LLM_1_MODEL_ID | `openai/gpt-oss-120b` |
| LLM_1_API_KEY | (key từ .env dòng LLM_1_API_KEY) |
| LLM_2_NAME | `qwen3-32b` |
| LLM_2_PROVIDER | `groq` |
| LLM_2_MODEL_ID | `qwen/qwen3-32b` |
| LLM_2_API_KEY | (key từ .env dòng LLM_2_API_KEY) |
| LLM_3_NAME | `Claude Sonnet 4` |
| LLM_3_PROVIDER | `bedrock` |
| LLM_3_MODEL_ID | `anthropic.claude-sonnet-4-20250514-v1:0` |
| TOP_K | `5` |
| ENABLE_RERANKER | `false` |

   - **Log**:
     - Log driver: `awslogs`
     - Options:
       - `awslogs-group`: `/ecs/newsrag-project`
       - `awslogs-region`: `ap-southeast-2`
       - `awslogs-stream-prefix`: `api`

4. **Create**

### F. Tạo ECS Service

1. Vào **ECS → Clusters → newsrag-cluster → Services → Create**
2. Config:
   - Launch type: `FARGATE`
   - Family: `newsrag-api` (chọn vừa tạo)
   - Revision: `LATEST`
   - Service name: `newsrag-api-service`
   - Desired tasks: `1`
   - **Next**
3. **Networking**:
   - VPC: `newsrag-vpc`
   - Subnets: chọn cả 2 public subnets (`ap-southeast-2a`, `ap-southeast-2b`)
   - Security group: chọn `newsrag-alb-sg`
   - Auto-assign public IP: `ENABLED`
   - Load balancer type: `Application Load Balancer`
     - **Create new** hoặc chọn `newsrag-api-alb` vừa tạo
     - Container: `api:8000`
     - Production listener: HTTP:80
     - Target group: `newsrag-api-tg` (chọn vừa tạo)
   - **Next → Next → Create**
4. Vào **Services** tab, đợi `RUNNING` (vài phút)

---

## IV. AWS CONSOLE — FRONTEND

### A. Push frontend lên S3

1. Vào **S3 → Create bucket**
   - Name: `newsrag-frontend-814808959551`
   - Region: `ap-southeast-2`
   - **Uncheck** "Block all public access" → tick "Block public access to buckets and objects granted through new access control lists (ACLs)"
   - **Create**
2. Mở bucket vừa tạo → **Upload**
   - Upload cả thư mục `frontend/dist/` từ máy local
3. Vào **Properties → Static website hosting → Edit → Enable**
   - Index document: `index.html`
   - Error document: `index.html`
   - **Save**

### B. Policy cho S3 (để CloudFront đọc được)

Vào **Permissions → Bucket Policy → Edit → Paste**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::newsrag-frontend-814808959551/*"
    }
  ]
}
```

> Có thể để public read tạm cho nhanh. Production nên dùng OAI.

### C. Tạo CloudFront

1. Vào **CloudFront → Create Distribution → Get started**
2. **Origin**:
   - Origin domain: chọn bucket `newsrag-frontend-814808959551`
   - Origin access: `Public` (đỡ phải setup OAI)
3. **Default cache behavior**:
   - Viewer protocol policy: `Redirect HTTP to HTTPS`
4. **Settings**:
   - Price class: `Use only North America and Europe` (PriceClass_100) — rẻ hơn
   - Default root object: để trống
   - **Create distribution**
5. Copy **Distribution domain name** (vd: `d123.cloudfront.net`)

### D. Build lại frontend với API URL đúng và deploy

Nếu đã build frontend lúc đầu với `http://localhost:8000` thì build lại với URL thật:

```bash
cd ~/AWS-Project/frontend

# Lấy ALB DNS name từ EC2 → Load Balancers
# ALB_DNS = newsrag-api-alb-xxxxxx.ap-southeast-2.elb.amazonaws.com

VITE_API_URL=http://<ALB_DNS> npm run build
```

Upload lại `dist/` vào S3 (xóa file cũ rồi upload lại).

---

## V. VERIFY

1. Test API: mở browser `http://<ALB_DNS>/health` → `{"status":"ok"}`
2. Test frontend: mở `https://<CloudFront_Domain>/` → thấy dashboard
3. Search thử → có kết quả

---

## CHEAT SHEET — lệnh Docker + AWS CLI (optional)

Nếu lười click web, mở terminal chạy 3 lệnh này sau khi có AWS CLI:

```bash
# 1. Push image
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com
docker tag newsrag-api:latest 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-api:latest
docker push 814808959551.dkr.ecr.ap-southeast-2.amazonaws.com/newsrag-api:latest

# 2. Sync frontend
aws s3 sync frontend/dist/ s3://newsrag-frontend-814808959551/ --delete

# 3. Invalidate CloudFront
aws cloudfront create-invalidation --distribution-id <CF_ID> --paths "/*"
```

> Lấy CF_ID từ CloudFront console.