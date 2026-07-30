# Từ Kafka đến SQS: Bài học khi chạy message broker trên EC2 cỡ nhỏ

## Mở bài

Dự án **News RAG** của tôi là một data pipeline tự động crawl tin tức từ các báo điện tử Việt Nam (VnExpress, Thanh Niên, VietnamNet), xử lý text, tạo embedding vector, và phục vụ truy vấn RAG (Retrieval-Augmented Generation) qua LLM.

Kiến trúc ban đầu (v1) trông khá chuẩn cho một project kiểu này:

```
Scrapy Crawler → Kafka (topic: news_raw) → Consumer → PostgreSQL
```

Lý do chọn Kafka là hợp lý: Scrapy crawl 3 nguồn báo song song, mỗi nguồn đẩy hàng trăm bài vào topic `news_raw` mỗi lần chạy. Kafka xử lý được throughput cao, giữ message history, và tách bạch producer/consumer rõ ràng. Mọi thứ lý thuyết đều đúng.

Vấn đề là tôi chạy Kafka trên một con **EC2 t3.small** (2 vCPU, 2GB RAM).

---

## Vấn đề: Kafka ăn RAM như thế nào

### Tại sao Kafka cần nhiều tài nguyên

Kafka không phải là một process nhẹ. Ngay cả với KRaft mode (bỏ Zookeeper), một broker cần:

- **Page cache cho log segments**: Kafka ghi message xuống disk theo log segments. Hiệu năng đọc phụ thuộc vào page cache của OS — phần RAM mà Linux dùng để cache file pages. Với 2GB RAM, gần như không còn gì cho page cache sau khi JVM reserve đủ bộ nhớ.
- **JVM heap**: Kafka broker chạy trên Java. Heap size mặc định cho production thường là 4–6GB. Trên t3.small, set JVM heap = 1GB thì broker chạy ì ọp, set > 1.5GB thì OS bị ép dùng swap.
- **Metadata management**: Controller maintaining partition leadership, ISR lists, topic metadata — đều consume memory.
- **Network buffers**: Mỗi partition replicas cần network buffer để replicate. Dù chỉ có 1 broker (không replicate), OS vẫn cần buffer cho network I/O.

### Triệu chứng tôi gặp phải

**1. OOM Killer**

Đây là thứ đầu tiên tôi thấy. Linux OOM killer (Out-Of-Memory Killer) là cơ chế của kernel — khi RAM hết, nó chọn process "ăn RAM nhất" để kill. Trên t3.small:

```
[684952.187156] Out of memory: Killed process 1234 (java) total-vm:3891428kB,
anon-rss:1621432kB, file-rss:0kB, shmem-rss:0kB
```

Kafka broker bị kill. Container restart. Lại bị kill. Loop.

**2. Container Crash Loop**

Kafka container (Docker/KRaft mode) liên tục crash. `docker logs` cho thấy broker khởi động, bắt đầu load log segments, rồi bị OOM kill trước khi hoàn tất. RetryPolicy của Docker Swarm hoặc `restart: always` chỉ tạo ra loop vô tận — broker chết, restart, lại chết, mỗi lần mất thêm 30–60 giây startup time.

**3. Latency tăng đột biến**

Khi broker không bị kill nhưng gần hết RAM, Linux bắt đầu dùng **swap**. Disk I/O cho swap chậm hơn RAM gấp hàng trăm lần. Mỗi `produce` request mất vài trăm毫秒 thay vì vài毫秒. Spider bị block vì `send_message` chờ response quá lâu. Crawl rate giảm từ ~50 bài/phút xuống còn ~10 bài/phút.

**4. Treo cứng khi load tăng**

Lúc chạy 3 spider cùng lúc (3 nguồn báo), throughput tăng đột ngột. Broker phải xử lý nhiều partition writes đồng thời. Trên 2GB RAM, spike load khiến system hoàn toàn freeze — SSH không login được, console AWS cần reboot instance.

### Nguyên nhân gốc

Phải thẳng thắn: **Kafka không "dở"**. Vấn đề là tôi chọn sai kích cỡ hạ tầng. Kafka là distributed streaming platform được thiết kế để chạy trên cluster 3+ nodes, mỗi node 8GB+ RAM. Tôi cố nhồi nó vào một t3.small với 2GB RAM — kết quả là đương nhiên.

Tuy nhiên, câu hỏi thực tế là: **pipeline này có cần một Kafka cluster không?**

---

## Ra quyết định: So sánh Kafka vs SQS

Trước khi quyết định, tôi liệt kê rõ trade-off:

| Tiêu chí | Kafka | Amazon SQS Standard |
|---|---|---|
| **Throughput** | Rất cao (hàng triệu msg/s) | ~300.000 msg/s |
| **Ordering** | Guaranteed within partition | Best-effort (không guarantee) |
| **Message retention** | Configurable (ngày–tuần) | 14 ngày max |
| **Consumer group** | Native, sophisticated | SQS group (dùng redrive policy) |
| **Fan-out** | Topic-based, native | Broadcast bằng SNS + SQS subscription |
| **Replay** | Offset-based, full replay | Không có — message xóa sau khi process |
| **Message size** | ~1MB (configurable) | 256KB (hoặc 2GB với SQS Extended Client) |
| **Operational overhead** | Tự quản lý cluster, monitoring, upgrade | Managed service, gần như zero ops |
| **Chi phí** | EC2 instance + EBS + network | ~$0.40/million requests |

### Đánh giá cho trường hợp cụ thể của tôi

Pipeline chạy **3 lần/ngày** (08:00, 14:00, 20:00). Mỗi lần crawl ~1000–2000 bài. Tổng message mỗi ngày: ~3000–6000. Đây là throughput **cực thấp** so với capacity của cả Kafka lẫn SQS.

**Kafka overkill** cho workload này. 99.99% năng lực của Kafka cluster bị lãng phí. Tôi đang trả tiền (và đau đớn về ops) cho thứ không cần.

**SQS phù hợp** khi:
- Message volume thấp đến trung bình
- Ordering không quan trọng (mỗi bài tin là independent event)
- Không cần replay history dài hạn
- Muốn giảm ops overhead xuống gần bằng không

**Kafka vẫn đúng** khi:
- Cần replay/audit log
- Ordering quan trọng (event sourcing, financial transaction)
- Multi-consumer independently consume same stream
- Throughput cực cao

Quyết định: **chuyển sang SQS**. Đây là trade-off, không phải upgrade.

---

## Quá trình migrate

### Thay đổi kiến trúc

v1 (Kafka):
```
Scrapy Crawler → KafkaPipeline (confluent-kafka) → Kafka topic "news_raw"
    → consumer/consumer.py (confluent_kafka consumer) → PostgreSQL
```

v2 (SQS):
```
Fargate Crawler → SQSPipeline (boto3) → Amazon SQS Standard
    → Lambda Consumer (trigger SQS) → Aurora PostgreSQL
```

### 1. Producer: KafkaPipeline → SQSPipeline

Trước (Kafka):
```python
# crawler/pipelines.py — v1
from confluent_kafka import Producer

class KafkaPipeline:
    def __init__(self):
        self.producer = Producer({
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
            'client.id': 'scrapy-crawler'
        })

    def process_item(self, item, spider):
        self.producer.produce(
            topic='news_raw',
            key=item['url'],
            value=json.dumps(dict(item)),
            callback=self._delivery_report
        )
        self.producer.poll(0)
        return item
```

Sau (SQS):
```python
# crawler/pipelines.py — v2
import json, os, boto3

class SQSPipeline:
    def __init__(self):
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.sqs = boto3.client('sqs', region_name=os.getenv('SQS_REGION', 'ap-southeast-2'))

    def process_item(self, item, spider):
        if not self.queue_url:
            spider.logger.warning("SQS_QUEUE_URL is not set!")
            return item
        message_body = json.dumps(dict(item), ensure_ascii=False)
        try:
            self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=message_body)
        except Exception as e:
            spider.logger.error(f"Failed to send message to SQS: {e}")
        return item
```

Thay đổi đáng chú ý:
- **Bỏ `confluent-kafka`**, dùng `boto3` (đã có sẵn cho AWS).
- **Không cần `_delivery_report` callback** — SQS `send_message` synchronous, raise exception nếu fail.
- **Message size**: JSON body của mỗi bài tin ~5–20KB, comfortably dưới 256KB limit của SQS.

### 2. Consumer: Python Script → Lambda

Trước (Kafka consumer — Python script chạy riêng):
```python
# consumer/consumer.py — v1 (đã xoá)
from confluent_kafka import Consumer, KafkaError

def run_consumer():
    consumer = Consumer({
        'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
        'group.id': 'news-consumer',
        'auto.offset.reset': 'earliest'
    })
    consumer.subscribe(['news_raw'])

    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            print(f"Consumer error: {msg.error()}")
            continue

        article = json.loads(msg.value().decode('utf-8'))
        url_hash = hashlib.sha256(article['url'].encode()).hexdigest()
        # INSERT into PostgreSQL...
```

Sau (Lambda + SQS trigger):
```python
# lambda_handlers/consumer (nằm trong Lambda deployment package)
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

Thay đổi cốt lõi:
- **Không còn loop vô hạn** (`while True: consumer.poll()`) — Lambda tự trigger khi có message.
- **Batch processing**: Lambda nhận 1–10 messages mỗi invocation (configurable — `batch_size` trong SQS event source mapping).
- **Idempotent**: `ON CONFLICT (url_hash) DO NOTHING` — dù message bị process 2 lần (do SQS at-least-once delivery), data không bị duplicate.
- **Xoá toàn bộ `consumer/consumer.py`** — file này không tồn tại nữa.

### 3. DLQ (Dead Letter Queue)

SQS có native DLQ support. Config trên AWS Console hoặc Terraform:

```
Main Queue → MaxReceiveCount: 3 → DLQ
```

Nếu message fail xử lý 3 lần (Lambda raise exception hoặc timeout), message tự động chuyển sang DLQ. So với Kafka, tôi phải tự implement retry logic bằng code — giờ AWS lo giúp.

### 4. Visibility Timeout

Mỗi message SQS có **visibility timeout** (default 30s) — sau khi Lambda nhận message, message "biến mất" khỏi queue trong khoảng thời gian này. Nếu Lambda xử lý xong và delete message → done. Nếu Lambda fail → message xuất hiện lại sau visibility timeout, retry.

Đây là cơ chế tương đương **consumer auto-commit** trong Kafka, nhưng tinh tế hơn: Kafka auto-commit có thể commit message trước khi xử lý xong (gây lost message), còn SQS visibility timeout liên kết trực tiếp với processing status.

---

## Khó khăn khi chuyển đổi

### 1. SQS không có consumer group kiểu Kafka

Trong Kafka, consumer group cho phép **parallel processing theo partition**: 10 partition + 10 consumer = mỗi consumer xử lý 1 partition. Load balance tự động.

SQS Standard không có khái niệm consumer group hay partition. Mỗi message chỉ được process 1 lần bởi 1 Lambda instance. Parallelism đến từ Lambda concurrency (default 1000), không từ partition count.

**Ảnh hưởng thực tế**: Với workload ~5000 messages/ngày, tôi không cần parallelism phức tạp. Nhưng nếu pipeline grow lên, SQS Standard vẫn scale tốt (AWS lo phần infra), trong khi Kafka tôi phải tự add partition + consumer.

### 2. Message size 256KB

Mỗi article content có thể dài 10–30KB (raw HTML text). Sau khi Scrapy parse, JSON body khoảng 5–20KB. Comfortably dưới 256KB.

Nhưng nếu cần gửi **full HTML content** (trước khi parse), một bài viết HTML đầy đủ có thể 200–500KB. Khi đó cần:
- **SQS Extended Client** (giới thiệu message lên S3, SQS chỉ chứa reference) — thêm dependency.
- Hoặc **parse trước trong crawler**, chỉ gửi data cần thiết.

Tôi chọn option 2 — chỉ gửi `{url, title, content, published_at, author}`. Đủ cho consumer, giữ message nhỏ.

### 3. Không có replay log

Kafka giữ message theo configurable retention (7 ngày, 30 ngày, v.v.). Tôi có thể re-consume từ offset cụ thể để fix data hoặc backfill.

SQS Standard: message bị xóa sau khi successfully process. Nếu consumer insert sai data, không có cách nào "replay" từ queue — phải fix trong database.

**Giải pháp**: Backup raw data vào S3 (S3 bucket là replay log của riêng tôi). Lambda consumer simultaneously write to Aurora + S3. Chi phí S3 gần như bằng không cho volume nhỏ.

### 4. Ordering không đảm bảo

SQS Standard là **best-effort ordering**. Nếu tôi cần guarantee rằng article A được process trước article B (ví dụ: A là parent page, B là sub-article), SQS Standard sẽ không đảm bảo.

Trong trường hợp của tôi, mỗi article là **independent event** — không có dependency giữa chúng. Ordering không quan trọng. Nếu cần ordering thực sự, dùng **SQS FIFO** — nhưng throughput bị giới hạn 300 msg/s (và chi phí đắt hơn).

### 5. Không có offset management

Kafka: tôi biết chính xác consumer đã process đến message nào (offset). Dễ debug, dễ pause/resume.

SQS: không có offset. Consumer chạy đến đâu thì đến. Nếu muốn pause, delete event source mapping. Muốn resume, tạo lại mapping. Không có khái niệm "resume từ offset 1234".

---

## Kết quả sau khi chuyển

### Về vận hành

| Chỉ số | v1 (Kafka trên t3.small) | v2 (SQS + Lambda) |
|---|---|---|
| **Crash次数** | 3–5 lần/ngày (OOM) | 0 |
| **Pipeline uptime** | ~60% (do crash loop) | ~99.9% |
| **Debug time** | 2–3 giờ/ngày (xử lý crash, restart) | ~0 (managed service) |
| **Deployment** | docker compose up + hope | Terraform apply |

### Về chi phí

| Component | v1 | v2 |
|---|---|---|
| **EC2 (Kafka)** | t3.small: ~$15/tháng | Bỏ |
| **SQS** | — | ~$0.01/tháng (5000 msg/ngày) |
| **Lambda (Consumer)** | — | ~$0.5/tháng |
| **Tổng** | ~$15 (chỉ EC2) | ~$0.51 |

Giảm **~97% chi phí** cho messaging layer. Tổng pipeline chi phí: từ ~$35/tháng xuống ~$21–26/tháng (bao gồm Aurora, Fargate, Bedrock, API Gateway).

### Về codebase

- Xoá `consumer/consumer.py` — 80 dòng code tự quản lý.
- Xoá `confluent-kafka` dependency.
- Thêm `boto3` SQS calls — 20 dòng trong `SQSPipeline`.
- Lambda handler — 30 dòng, không cần loop, không cần offset management.

Tổng cộng: **giảm ~100 dòng code**, bỏ 1 dependency, bỏ 1 service cần tự vận hành.

---

## Bài học rút ra

### 1. Chọn đúng công cụ cho đúng kích cỡ

Kafka là công cụ tuyệt vời — cho đúng bài toán. Một pipeline crawl 5000 bài/ngày không cần distributed streaming platform. SQS Standard, với managed service và chi phí gần bằng không, là lựa chọn đúng đắn cho workload này.

Nếu pipeline scale lên 100.000+ messages/ngày, cần event replay, multi-consumer independently consume — lúc đó quay lại Kafka (hoặc Amazon Kinesis/MSK) mới hợp lý.

### 2. Managed service = bỏ qua operational overhead

Với Kafka, tôi dành 2–3 giờ/ngày để: restart broker, fix OOM, monitor disk, plan capacity. Với SQS, tôi dành 0 giờ. Thời gian đó tôi dùng để improve pipeline, viết feature mới, hoặc đơn giản là nghỉ ngơi.

### 3. Đừng cố fit distributed system vào single-node

Kafka, Cassandra, Elasticsearch — đều là distributed systems được thiết kế để chạy trên cluster. Cố nhồi vào 1 node nhỏ không phải là "tiết kiệm" — đó là tự tạo pain.

### 4. Trade-off rõ ràng, không có free lunch

SQS Standard không có ordering guarantee, không có replay log, không có consumer group phức tạp. Tôi chấp nhận những trade-off này vì workload của tôi không cần chúng. Nếu bạn cần chúng, hãy dùng đúng công cụ phù hợp (Kafka, Kinesis, hoặc SQS FIFO cho ordering).

### 5. Đôi khi "đơn giản hơn" = "tốt hơn"

Pipeline v1: Crawler → Kafka → Consumer → DB. Bốn component, một trong số đó cần quản lý cluster.

Pipeline v2: Crawler → SQS → Lambda → DB. Bốn component, tất cả managed services.

Ít component hơn, ít failure modes hơn, ít ops hơn, ít chi phí hơn. Đôi khi best architecture là architecture bỏ đi được nhiều nhất.

---

*Bài viết dựa trên trải nghiệm thực tế với dự án News RAG Pipeline on AWS. Toàn bộ code source có trên GitHub.*
