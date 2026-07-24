# AWS Migration Task List

## Phase 1: IAM Roles & Policies
- `[x]` 1.1 Tạo Lambda Execution Role (`newsrag-lambda-execution-role`)
- `[x]` 1.2 Attach policies: `AWSLambdaBasicExecutionRole`, `AWSLambdaVPCAccessExecutionRole`
- `[x]` 1.3 Tạo + attach custom policy (`newsrag-custom-policy`): Bedrock + SQS + CloudWatch
- `[x]` 1.4 Tạo ECS Execution Role (`newsrag-ecs-execution-role`)
- `[x]` 1.5 Attach policy: `AmazonECSTaskExecutionRolePolicy`
- `[x]` 1.6 Tạo ECS Task Role (`newsrag-ecs-task-role`) + attach custom policy
- `[x]` 1.7 Security Group cho ECS (`sg-0330980a3f9ca4eb0`) — đã tồn tại
- `[x]` 1.8 RDS SG cho phép ECS SG truy cập port 5432 — đã tồn tại
- `[x]` 1.9 Tạo EventBridge Role (`newsrag-eventbridge-role`) + attach policy

## Phase 2: SQS
- `[x]` 2.1 Tạo Dead Letter Queue (`newsrag-raw-news-dlq`)
- `[x]` 2.2 Tạo Main Queue (`newsrag-raw-news`) với DLQ redrive policy

## Phase 3: pgvector
- `[ ]` 3.1 Kích hoạt pgvector extension trên Aurora (cần user kết nối psql)

## Phase 4: ECR
- `[x]` 4.1 Tạo ECR Repository (`newsrag-crawler`)

## Phase 5: ECS Fargate
- `[x]` 5.1 Tạo ECS Cluster (`newsrag-cluster`)
- `[x]` 5.2 Tạo CloudWatch Log Group (`/ecs/newsrag-crawler`, retention 7 ngày)
- `[x]` 5.3 Đăng ký Task Definition (`newsrag-crawler:1`)

## Phase 6: Lambda Functions
- `[ ]` 6.1 Tạo Lambda Consumer (cần viết handler code + package)
- `[ ]` 6.2 Tạo Lambda ETL (cần viết handler code + package)
- `[ ]` 6.3 Tạo Lambda RAG API (cần viết handler code + package)
- `[ ]` 6.4 Tạo SQS trigger cho Consumer

## Phase 7: API Gateway
- `[ ]` 7.1 Tạo REST API
- `[ ]` 7.2 Tạo resource + method + Lambda integration
- `[ ]` 7.3 Deploy stage

## Phase 8: EventBridge
- `[x]` 8.1 Tạo Crawler schedule rule (`cron 01:00 UTC`)
- `[x]` 8.2 Tạo ETL schedule rule (`cron 02:00 UTC`)
- `[x]` 8.3 Add Crawler target → ECS Fargate
- `[ ]` 8.4 Add ETL target → Lambda (sau khi Lambda ETL tạo xong)

## Phase 9: .env
- `[x]` 9.1 Comment out Qdrant → thêm pgvector config
- `[x]` 9.2 Comment out Kafka → thêm SQS config
- `[x]` 9.3 Comment out Bedrock API Key → chuyển auth_mode=auto
