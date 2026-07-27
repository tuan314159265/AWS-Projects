# Kiểm soát AWS Console + Giải pháp Bedrock miễn phí

## 1. Tại sao Console không thấy gì?

**Nguyên nhân: Bạn đang xem sai Region!**

Tất cả dịch vụ đã tạo ở **`ap-southeast-2` (Asia Pacific - Sydney)**. Trên Console:

1. Nhìn góc **trên cùng bên phải** (cạnh tên user)
2. Click vào dropdown Region
3. Chọn **Asia Pacific (Sydney) `ap-southeast-2`**

Sau khi chọn đúng region, bạn sẽ thấy tất cả dịch vụ.

## 2. Links trực tiếp tới từng dịch vụ

> [!TIP]
> Bookmark các link này để truy cập nhanh. Tất cả đều trỏ tới region `ap-southeast-2`.

| Dịch vụ | Link Console |
|---------|-------------|
| **RDS (Aurora)** | [https://ap-southeast-2.console.aws.amazon.com/rds/home?region=ap-southeast-2#databases:](https://ap-southeast-2.console.aws.amazon.com/rds/home?region=ap-southeast-2#databases:) |
| **SQS Queues** | [https://ap-southeast-2.console.aws.amazon.com/sqs/v3/home?region=ap-southeast-2#/queues](https://ap-southeast-2.console.aws.amazon.com/sqs/v3/home?region=ap-southeast-2#/queues) |
| **ECR Repositories** | [https://ap-southeast-2.console.aws.amazon.com/ecr/repositories?region=ap-southeast-2](https://ap-southeast-2.console.aws.amazon.com/ecr/repositories?region=ap-southeast-2) |
| **ECS Clusters** | [https://ap-southeast-2.console.aws.amazon.com/ecs/v2/clusters?region=ap-southeast-2](https://ap-southeast-2.console.aws.amazon.com/ecs/v2/clusters?region=ap-southeast-2) |
| **Lambda Functions** | [https://ap-southeast-2.console.aws.amazon.com/lambda/home?region=ap-southeast-2#/functions](https://ap-southeast-2.console.aws.amazon.com/lambda/home?region=ap-southeast-2#/functions) |
| **EventBridge Rules** | [https://ap-southeast-2.console.aws.amazon.com/events/home?region=ap-southeast-2#/rules](https://ap-southeast-2.console.aws.amazon.com/events/home?region=ap-southeast-2#/rules) |
| **IAM Roles** | [https://console.aws.amazon.com/iam/home#/roles](https://console.aws.amazon.com/iam/home#/roles) (IAM là global) |
| **VPC** | [https://ap-southeast-2.console.aws.amazon.com/vpcconsole/home?region=ap-southeast-2#vpcs:](https://ap-southeast-2.console.aws.amazon.com/vpcconsole/home?region=ap-southeast-2#vpcs:) |
| **CloudWatch Logs** | [https://ap-southeast-2.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#logsV2:log-groups](https://ap-southeast-2.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-2#logsV2:log-groups) |

> [!NOTE]
> **Bedrock** đang ở region `ap-southeast-1` (Singapore) — khác region!
> Link: [https://ap-southeast-1.console.aws.amazon.com/bedrock/home?region=ap-southeast-1](https://ap-southeast-1.console.aws.amazon.com/bedrock/home?region=ap-southeast-1)

---

## 3. Giải pháp Bedrock miễn phí cho Lambda trong VPC

### Vấn đề
- Lambda phải join VPC để kết nối Aurora (private network)
- Lambda trong VPC **không có Internet** mặc định
- Lambda cần Internet để gọi **Bedrock API** (ap-southeast-1) và **Groq API**
- **NAT Gateway** giải quyết vấn đề nhưng tốn **~$32/tháng** → không phù hợp serverless

### Giải pháp: VPC Endpoints (miễn phí*)

> [!IMPORTANT]
> VPC Interface Endpoints chỉ tính phí **$0.01/GB data processed** — với lượng data nhỏ của dự án (vài MB embedding/ngày), chi phí gần như **$0**.

Cần tạo **2 loại VPC Endpoints**:

| Endpoint | Mục đích | Loại |
|----------|---------|------|
| **Bedrock Runtime** | Gọi Bedrock Embed API | Interface Endpoint |
| **SQS** | Lambda trigger từ SQS | Interface Endpoint |
| **CloudWatch Logs** | Lambda ghi logs | Interface Endpoint |

> [!WARNING]
> **Vấn đề cross-region**: Bedrock ở `ap-southeast-1`, Lambda ở `ap-southeast-2`. VPC Endpoint chỉ hoạt động **cùng region**. Có 2 cách giải quyết:
>
> **Cách A (Khuyến nghị)**: Chuyển Bedrock sang `ap-southeast-2` nếu model `amazon.titan-embed-text-v2:0` có sẵn ở Sydney
>
> **Cách B**: Giữ RDS publicly accessible + Lambda **không join VPC** → Lambda tự do gọi Internet → không cần NAT/VPC Endpoint

### Cách B đơn giản nhất cho Serverless (Khuyến nghị)

Vì RDS hiện đã **publicly accessible** (`PubliclyAccessible: true` từ output trước), Lambda không cần join VPC:

```
Lambda (public Internet) ──► Aurora RDS (publicly accessible, port 5432)
                          ──► Bedrock (ap-southeast-1, qua Internet)
                          ──► Groq API (qua Internet)
```

**Ưu điểm:**
- ✅ Miễn phí hoàn toàn (không NAT, không VPC Endpoint)
- ✅ Lambda gọi được Bedrock cross-region
- ✅ Lambda gọi được Groq/external API
- ✅ Đơn giản nhất

**Bảo mật:**
- RDS đã có Security Group chặn truy cập (chỉ cho phép từ ECS SG)
- Cần thêm rule cho phép Lambda truy cập từ Internet

### Lệnh cần chạy (Cách B)

```powershell
# Cho phép truy cập RDS từ bất kỳ đâu trên port 5432 (Lambda public)
# Hoặc tốt hơn: tạo SG riêng cho Lambda
aws ec2 authorize-security-group-ingress --group-id sg-06481a478ca45da1f --protocol tcp --port 5432 --cidr 0.0.0.0/0 --profile default
```

> [!CAUTION]
> Mở port 5432 cho `0.0.0.0/0` cần đảm bảo password DB đủ mạnh. Trong môi trường production, nên dùng VPC + VPC Endpoints.
