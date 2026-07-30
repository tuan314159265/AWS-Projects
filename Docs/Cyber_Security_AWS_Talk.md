# Cyber Security x AWS: Career Paths & Automated Incident Response on the Cloud

## Giới thiệu
Bài nói này được xây dựng trong khuôn khổ chương trình **First Cloud Journey (FCJ)**, nhằm cung cấp góc nhìn thực tế về bảo mật đám mây — từ lộ trình nghề nghiệp, chiến thuật tấn công/phòng thủ, đến demo trực tiếp quy trình phát hiện và cô lập threat tự động trên AWS.

---

## Phần 1: Thực tế về Bảo mật Đám mây — Myths vs. Facts & AWS Shared Responsibility Model

### Myths vs. Facts

| Myth | Fact |
|---|---|
| "Cloud không an toàn bằng on-premise" | AWS vận hành với hàng trăm control bảo mật đẳng cấp enterprise — nhưng **trách nhiệm của bạn** (cấu hình IAM, network ACL, encryption) mới là thứ quyết định. |
| "Lên cloud là AWS lo hết bảo mật" | Sai. AWS chỉ bảo vệ *của cloud* — bạn lo *trong cloud* (dữ liệu, identity, OS config). |
| "Cần đội ngũ security khủng mới dùng cloud được" | AWS cung cấp sẵn GuardDuty, Security Hub, Config, WAF — tích hợp vài click, không cần build từ zero. |
| "Pentest cloud bị cấm" | AWS cho phép pentest hầu hết services mà không cần xin phép trước (trừ VMware, RDS Custom). |

### AWS Shared Responsibility Model

```
┌──────────────────────────────────────────────┐
│        CUSTOMER (bạn)                         │
│  - Data, Identity & Access Management (IAM)   │
│  - OS, Network & Firewall config              │
│  - Encryption at rest / in transit            │
│  - Application code vulnerabilities           │
├──────────────────────────────────────────────┤
│        AWS (đám mây)                          │
│  - Compute, Storage, Database physical infra  │
│  - Networking hardware                        │
│  - Managed services (RDS, S3, Lambda runtime)  │
└──────────────────────────────────────────────┘
```

**Nguyên tắc vàng:** Dịch vụ càng managed (RDS, Lambda, S3), AWS lo càng nhiều. Dịch vụ càng raw (EC2, EKS worker nodes), bạn lo càng nhiều.

---

## Phần 2: 5 Pillars — Lộ trình Nghề nghiệp Bảo mật Cloud

### [1] Red Team & Cloud Pentest

**Mục tiêu:** Mô phỏng tấn công để lỗ hổng lộ ra trước khi attacker thật khai thác.

**Kỹ thuật tấn công phổ biến trên AWS:**

- **IAM Privilege Escalation:** Lợi dụng policy quá rộng (`Action: "*"`, `Resource: "*"`) hoặc trust policy cho phép assume role chéo.
  ```
  # Attacker chiếm được IAM user có s3:GetObject trên bucket chứa Lambda code
  # -> Đọc code -> Tìm thấy AWS key hardcode -> leo lền role mạnh hơn
  ```
- **Misconfigurations — S3 bucket public:** Bucket cho phép `ListBucket` và `GetObject` mà không có blocking policy.
- **Metadata SSRF** (Instance Metadata Service): Tấn công ứng dụng web để đọc `http://169.254.169.254/latest/meta-data/iam/security-credentials/` — lấy luôn temporary credential của EC2.
- **CloudTrail log forgery:** Nếu không bật log integrity validation, attacker có thể xoá/sửa trail để xoá dấu vết.

**Tool hay dùng:** `ScoutSuite`, `Pacu`, `CloudSploit`, `CrackMapExec` (AWS module), custom python scripts với boto3.

---

### [2] Blue Team & Cloud Defense

**Mục tiêu:** Phát hiện tấn công sớm, ngăn chặn thiệt hại, điều tra pháp y.

**Dịch vụ AWS cốt lõi:**

| Dịch vụ | Vai trò |
|---|---|
| **GuardDuty** | Phát hiện bất thường — API call lạ, crypto miner, port scan, credential compromised. |
| **CloudTrail** | Ghi lại mọi API call của AWS — "black box" cho security investigation. |
| **Detective** | Phân tích nguyên nhân gốc — visual graph các resource liên quan đến finding. |
| **Security Hub** | Trung tâm tổng hợp findings từ GuardDuty, Inspector, Config, và third-party. |
| **Config** | Theo dõi thay đổi cấu hình resource — phát hiện drift khỏi baseline. |

**Quy trình response điển hình:**

```
GuardDuty finding (crypto miner detected)
  → Security Hub aggregation
    → EventBridge rule trigger
      → Lambda tự động cô lập EC2 (thay SG)
        → SNS/SQS gửi alert
          → Slack/Telegram về Security team
```

**Forensic investigation:**
1. Xác định timeline từ CloudTrail — ai, khi nào, từ IP nào, gọi API gì.
2. Lấy EBS snapshot của instance bị compromise — phân tích memory và disk.
3. Kiểm tra VPC Flow Logs — kẻ tấn công kết nối đi đâu, gửi dữ liệu ra ngoài không.

---

### [3] Purple Team

**Mục tiêu:** Red và Blue không hoạt động riêng rẽ — Purple là vòng lặp phản hồi liên tục.

**Vòng lặp Continuous Feedback:**

```
Red Team phát hiện lỗ hổng mới
  → Chuyển kỹ thuật cho Blue Team
    → Blue xây detection rule (GuardDuty custom, Athena query)
      → Red thử lại xem còn qua được không
        → Nếu vượt được → quay lại refine rule
          → Nếu bị chặn → cập nhật knowledge base
```

**Lợi ích:**
- Detection rule luôn được test thực chiến, không chỉ "hy vọng là nó chạy".
- Giảm thời gian Mean Time to Detect (MTTD) và Mean Time to Respond (MTTR).
- Phát hiện blind spot: team defense tưởng có detection nhưng thực tế không bắt được.

---

### [4] DevSecOps Engineer

**Mục tiêu:** Tự động hoá bảo mật vào CI/CD — Security as Code.

**Nguyên tắc:**

```
─── Commit ──→ SAST (CodeQL/Semgrep) ──→ IaC Scan (Checkov/TfSec) ──→ Build ──→ Image Scan (Trivy) ──→ Deploy ──→ Post-deploy Scan ──→ 
                 │                          │                           │            │                         │
                 └── Fail nếu               └── Fail nếu S3             └── Fail     └── Fail nếu             └── GuardDuty +
                      có secret                bucket public ACL            nếu high      critical CVE           Security Hub
                      trong code                                             CVE                                           
```

**Tool AWS hỗ trợ:**
- **CodePipeline + CodeBuild** — pipeline gốc.
- **GuardDuty** — phát hiện threat ở runtime.
- **IAM Access Analyzer** — phát hiện policy public/chéo.
- **KMS + Secrets Manager** — quản lý secret tập trung, không hardcode.

**Ví dụ policy Checkov check Terraform:**
```hcl
# checkov:skip=CKV_AWS_21:S3 versioning chưa cần ở dev
resource "aws_s3_bucket" "data" {
  bucket = "newsrag-data"
  # checkov:skip=CKV_AWS_18:Access logging chưa triển khai
}
```

---

### [5] Cloud Security Architect

**Mục tiêu:** Thiết kế hệ thống an toàn ngay từ đầu — security-by-design.

**Tư duy kiến trúc cốt lõi:**

| Nguyên tắc | Áp dụng trên AWS |
|---|---|
| **Least Privilege** | IAM policy chỉ cấp quyền tối thiểu. Không dùng `"Action": "*"`. |
| **Defense in Depth** | Network layer (SG/NACL) + Identity layer (IAM) + Data layer (KMS) — nhiều lớp bảo vệ. |
| **Zero Trust** | Không tin bất kỳ request nào — xác thực tất cả, kể cả trong VPC. |
| **Shift Left** | Check bảo mật từ lúc viết code, không đợi deploy xong mới scan. |

**Mô hình tham khảo:**
```
Internet
    │
    ▼
CloudFront (WAF — SQLi, XSS blocking)
    │
    ▼
ALB (HTTPS only, SG chỉ cho phép CloudFront)
    │
    ▼
ECS Fargate (IAM task role riêng cho từng service)
    │
    ▼
RDS (encrypted at rest + transit, SG chỉ cho phép từ ECS)
```

---

## Phần 3: Live Demo — Kali Linux vs. AWS EC2

### Kịch bản

1. **Red Team**: Attacker dùng Kali Linux quét subnet AWS, tìm EC2 có SSH public + user `ubuntu` với password yếu → chiếm được shell → tải crypto miner chạy ngầm.

2. **Blue Team (tự động)**: GuardDuty phát hiện:
   - `UnauthorizedAccess:EC2/SSHBruteForce` — brute force SSH
   - `CryptoCurrency:EC2/BitcoinTool.B!DNS` — DNS query đến pool crypto
   → Security Hub aggregation → EventBridge rule → Lambda trigger.

3. **DevSecOps workflow** — Lambda thực thi:
   ```
   1. Ghi lại CloudTrail event và lấy metadata instance
   2. Gửi Telegram alert kèm thông tin: [instance-id, region, user, IP attacker, finding type]
   3. Thay đổi Security Group — thu hồi toàn bộ inbound access (network isolation)
   4. Tạo EBS snapshot để phục vụ forensic sau này
   5. Gửi confirmation về Telegram
   ```

4. **Kết quả:** Crypto miner bị cô lập trong vòng vài giây, không thể tiếp tục đào coin, dữ liệu disk được snapshot để phân tích.

### Luồng response (sơ đồ)

```
[GuardDuty] crypto miner detected
    │
    ▼
[EventBridge] finding matched rule "auto-isolate-crypto"
    │
    ▼
[Lambda] auto-isolate-instance
    ├── revoke_security_group_ingress → cô lập network
    ├── create_ebs_snapshot → forensic
    ├── send_telegram_alert → thông báo
    │
    ▼
[Complete] MTTR: vài giây
```

---

## Phần 4: Roadmap cho Beginner (FCJ)

### Lộ trình học (từ 0 đến có job)

```
Tháng 1-2: Nền tảng
├── AWS Cloud Practitioner Essentials
├── Mạng căn bản (VPC, subnet, route table, SG/NACL)
├── IAM (user, group, role, policy, trust policy)
└── Thực hành: dựng VPC 2-tier, SSH vào EC2 qua bastion host

Tháng 3-4: Chuyên sâu bảo mật
├── AWS Security Hub, GuardDuty, CloudTrail, Config
├── Kali Linux cơ bản — nmap, hydra, metasploit
├── Terraform — IaC, checkov/tfsec scan
└── Thực hành: dựng môi trường honeypot, trigger GuardDuty finding

Tháng 5-6: Automation & Response
├── Lambda + EventBridge — tự động response
├── Docker + ECS Fargate
├── CI/CD pipeline (CodePipeline)
└── Thực hành: xây dựng auto-isolation giống demo
```

### Chứng chỉ nên lấy

| Level | Chứng chỉ |
|---|---|
| Beginner | **AWS Cloud Practitioner** |
| Associate | **AWS Solutions Architect — Associate** + **Security Specialty** |
| Professional | **AWS Security — Specialty** + **AWS DevOps Engineer — Professional** |

### Lời khuyên cho sinh viên FCJ

1. **Lab là chính** — đọc 10 trang docs không bằng tự tay dựng 1 EC2 bị hack rồi tự response.
2. **Học IAM trước** — 80% lỗ hổng cloud đến từ IAM misconfiguration.
3. **Dùng AWS Free Tier** — đa số dịch vụ security (GuardDuty 30d free, CloudTrail free 1 trail) không tốn phí.
4. **Xây portfolio** — ghi lại quá trình: dựng pipeline, phát hiện threat, tự động response. Code public trên GitHub.
5. **Tham gia cộng đồng** — AWS User Group, FCJ Discord, CTF như AWS Cloud Quest hay Flaws.Cloud.

---

## Phần 5: Q&A & Discussion

### Câu hỏi thường gặp

**H: Có cần biết hacking trước khi học cloud security không?**
K: Không. Học AWS trước (IAM, VPC, compute cơ bản), sau đó học tấn công để hiểu cách phòng thủ.

**H: Nên bắt đầu với tool nào?**
K: AWS Console → CloudTrail → GuardDuty → Security Hub. Hiểu log trước, automation sau.

**H: Làm sao pentest AWS mà không bị khoá account?**
K: Dùng account riêng (không chạm production). Dùng tool trong allowed list của AWS. Không DoS.

**H: Nên học Kali Linux hay chỉ cần AWS?**
K: Cả hai. Kali để hiểu attacker nghĩ gì. AWS để hiểu hạ tầng. Purple là sự kết hợp.

---

## Tài liệu tham khảo

- [AWS Shared Responsibility Model](https://aws.amazon.com/compliance/shared-responsibility-model/)
- [GuardDuty Finding Types](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_finding-types.html)
- [Flaws.Cloud — AWS CTF](http://flaws.cloud/)
- [AWS Security Workshop](https://www.wellarchitectedlabs.com/security/)
- [Checkov IaC Scanning](https://www.checkov.io/)
