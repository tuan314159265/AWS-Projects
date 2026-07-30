# API Specification — News RAG Pipeline on AWS

**Phiên bản:** 1.0  
**Loại:** CLI + Python Module Interface (không phải REST API)  
**Backend Framework:** Python stdlib + Scrapy + LangChain

> **Ghi chú:** Dự án hiện tại không có REST/HTTP API. Giao tiếp giữa các module thông qua CLI entrypoint (`main.py`) và Python module calls (`search/engine.py`). Kiến trúc v2 (`Docs/Pipeline_v3.md`) có thiết kế Lambda RAG API + API Gateway nhưng chưa implement.

---

## 1. CLI Interface (`main.py`)

Entrypoint chính của pipeline. Hỗ trợ argparse với tham số `--mode`.

### Usage
```bash
python main.py --mode {crawl|etl|vectorize|full|auto}
```

### Mode Reference

| Mode | Chức năng | Luồng xử lý |
|------|-----------|-------------|
| `crawl` | Crawl tin tức + Kafka producer [v1 legacy] | Khởi chạy `NewsRAGSpider` cho từng URL → `KafkaPipeline` đẩy vào topic `news_raw` |
| `etl` | ETL vào Star Schema | Đọc dữ liệu từ file `data/articles.json` → clean HTML → chunk văn bản (RecursiveCharacterTextSplitter, 800/150) → insert vào dimension/fact tables |
| `vectorize` | Embedding → Qdrant | Load SentenceTransformer → đọc chunks từ PostgreSQL → embed batch 64 → upsert Qdrant batch 256 |
| `full` | Pipeline hoàn chỉnh | crawl → etl → vectorize (tuần tự) |
| `auto` | Tự động 3 ca/ngày | Lên lịch chạy full pipeline lúc 08:00, 14:00, 20:00 |

### Entrypoint Flow (`main.py`)

```
main.py --mode crawl
  └── do_crawl_stage()
      └── run_spider(url)      [Process × N: Scrapy Spider → data/articles.json]
                              (Luồng Kafka consumer đã được loại bỏ ở v2. Xem CHANGELOG.md)

main.py --mode etl
  └── run_etl_warehouse(limit) → etl_warehouse.py
      ├── load_schema()         [Khởi tạo bảng Star Schema]
      └── process_articles()    [Clean → chunk → insert]

main.py --mode vectorize
  └── run_vectorization(limit) → vectorize.py
      ├── EmbeddingModel.load() [SentenceTransformer]
      └── QdrantClient.upsert() [Batch 256]

main.py --mode full
  └── run_full_pipeline()
      ├── do_crawl_stage()
      └── do_balance_etl_and_vectorize() [Luân phiên ETL ↔ vectorize]
```

---

## 2. Module Interface (Python API)

### `search/engine.py` — Pipeline

```python
class Pipeline:
    def ask(
        query: str,
        model: str | None = None,
        is_vanilla: bool = False
    ) -> GeneratorResponse
    #     query:         Câu hỏi người dùng (tiếng Việt)
    #     model:         Tên model (optional, default từ env MODEL_1_NAME)
    #     is_vanilla:    False = RAG prompt, True = raw LLM (không context)
    #     Returns:       GeneratorResponse { query, summary, results, total, duration_ms }
```

### `search/retriever.py` — Retriever

```python
class Retriever:
    def search(query: str) -> list[SearchHit]
    #     query:    Câu hỏi người dùng
    #     Returns:  List[SearchHit] từ Qdrant vector search, top_k mặc định = MODEL_1_NAME.top_k
    #
    # Flow:
    #   1. SentenceTransformer.encode(query) → vector 384-dim
    #   2. QdrantClient.search(collection, vector, limit=top_k)
    #   3. Trả về List[SearchHit] (id, title, content, url, score, metadata)
```

### `search/generator.py` — GeneratorRegistry

```python
class GeneratorRegistry:
    def get_generator(identifier: str) -> BaseGenerator
    #     identifier:  Tên model (e.g., "qwen3-8b-instant")
    #     Returns:     BaseGenerator instance

    def list_generators() -> list[dict]
    #     Returns:     [{"identifier": ..., "model_name": ..., "provider": ...}, ...]

    def generate_with_fallback(
        query: str,
        hits: list[SearchHit],
        identifier: str,
        fallback_identifiers: list[str] | None = None
    ) -> str
    #     query:       Câu hỏi gốc
    #     hits:        Kết quả từ Retriever.search()
    #     identifier:  Model ưu tiên
    #     fallbacks:   Danh sách fallback (mặc định: các model còn lại)
    #     Returns:     Câu trả lời từ LLM
    #     Fallback flow: identifier → fallback_identifiers → "Xin lỗi..."
```

---

## 3. LLM Provider Contract

### BaseGenerator (Abstract Class)

```python
class BaseGenerator(ABC):
    llm: BaseLLM              # LangChain LLM instance
    prompt: ChatPromptTemplate # Prompt template từ prompts.py

    @abstractmethod
    def _init_llm() -> BaseLLM
    #     Khởi tạo LLM client theo provider

    def generate(
        self,
        query: str,
        context: str
    ) -> str
    #     query:    Câu hỏi
    #     context:  Nội dung từ Retriever (format: "title: ...\ncontent: ...")
    #     Returns:  Câu trả lời (đã strip <think> tags)
```

### Implementations

| Provider | Class | LangChain Backend | API Key Env |
|----------|-------|-------------------|-------------|
| Groq | `GroqGenerator` | `ChatGroq` | `MODEL_*_API_KEY` |
| Google | `GoogleGenerator` | `ChatGoogleGenerativeAI` | `MODEL_*_API_KEY` |
| Ollama | `OllamaGenerator` | `ChatOllama` | Không cần key |
| OpenAI | `OpenAIGenerator` | `ChatOpenAI` | `MODEL_*_API_KEY` |

### Provider Discovery

```python
GeneratorRegistry._PROVIDER_MAP = {
    "groq": GroqGenerator,
    "google": GoogleGenerator,
    "ollama": OllamaGenerator,
    "openai": OpenAIGenerator,   # Cũng dùng cho SiliconFlow
}
```

Provider được xác định qua biến môi trường `MODEL_{N}_PROVIDER` trong `.env`.

---

## 4. Data Models

### `search/schemas.py`

```python
class SearchHit(BaseModel):
    id: str                   # UUID5: article_{article_id}_chunk_{chunk_index}
    title: str                # Tiêu đề bài báo
    content: str              # Nội dung chunk
    url: str                  # URL bài báo gốc
    score: float              # Cosine similarity (Qdrant)
    metadata: dict            # Payload bổ sung từ Qdrant

class GeneratorResponse(BaseModel):
    query: str                # Câu hỏi gốc
    summary: str | None       # Câu trả lời từ LLM (None nếu lỗi)
    results: list[SearchHit]  # Danh sách chunks liên quan
    total: int                # Số lượng chunks trả về
    duration_ms: float        # Thời gian xử lý (ms)
```

### `search/config.py`

```python
class ModelConfig(BaseModel):
    embedding_model: str = "BAAI/bge-small-en-v1.5"  # Env: EMBEDDING_MODEL
    embedding_size: int = 384                          # Env: EMBEDDING_SIZE
    top_k: int = 20                                    # Env: TOP_K

class LLMInstanceConfig(BaseModel):
    name: str                        # MODEL_{N}_NAME
    model_id: str                    # MODEL_{N}_MODEL_ID
    provider: str                    # MODEL_{N}_PROVIDER
    api_key: str                     # MODEL_{N}_API_KEY
    temperature: float = 0.3         # MODEL_{N}_TEMPERATURE
    max_tokens: int = 2048           # MODEL_{N}_MAX_TOKENS

class SearchConfig(BaseModel):
    qdrant_host: str                 # Env: QDRANT_HOST
    qdrant_port: int = 6333          # Env: QDRANT_PORT
    qdrant_api_key: str              # Env: QDRANT_API_KEY
    qdrant_collection: str           # Env: QDRANT_COLLECTION_NAME
```

---

## 5. Error Handling

| Tình huống | Cách xử lý | Module |
|-----------|-----------|--------|
| Mất kết nối Kafka | Consumer reconnect + retry (v1 legacy, đã xoá) | `consumer.py` (removed) |
| Không tìm thấy kết quả Qdrant | Fallback "Xin lỗi, không tìm thấy thông tin..." | `engine.py` |
| LLM API fail | Fallback chain model → "Xin lỗi, hiện tại không thể..." | `generator.py` |
| Database connection lost | psycopg2 InterfaceError → reconnect | `consumer.py`, `etl_warehouse.py` |
