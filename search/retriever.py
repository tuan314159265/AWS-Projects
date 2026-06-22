import gc
import threading
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from .config import settings
from .logger_setup import logger
from .schemas import SearchHit


class Retriever:
    """
    Lightweight dense-only retriever. No reranking, no sparse vectors.
    Uses sentence-transformers for embedding and Qdrant for vector search.
    """

    _instance = None
    _lock = threading.Lock()
    _is_initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Retriever, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        with self.__class__._lock:
            if self._is_initialized:
                return
            self._initialize()
            self.__class__._is_initialized = True

    def _initialize(self):
        try:
            logger.info(f"Initializing embedding model: {settings.model.embedding}")
            self.embedding_model = SentenceTransformer(settings.model.embedding)

            logger.info(f"Connecting to Qdrant: {settings.search.qdrant_url}")
            self.qdrant_client = QdrantClient(
                url=settings.search.qdrant_url,
                port=settings.search.port,
                api_key=settings.search.api_key,
                grpc_port=settings.search.grpc_port,
                timeout=60
            )
            logger.info("Retriever initialized successfully.")
        except Exception as e:
            logger.error(f"Retriever init failed: {e}")
            raise

    def search(self, query: str) -> List[SearchHit]:
        try:
            logger.info(f"Searching: {query}")
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True).tolist()

            results = self.qdrant_client.search(
                collection_name=settings.search.collection_name,
                query_vector=query_embedding,
                limit=settings.model.top_k
            )

            search_hits = []
            for result in results:
                payload = result.payload or {}
                hit = SearchHit(
                    id=str(result.id),
                    title=str(payload.get("title", "No Title")),
                    content=str(payload.get("content", "")),
                    url=str(payload.get("url", "#")),
                    score=result.score if result.score else 0.0,
                    metadata={k: v for k, v in payload.items()
                              if k not in {"title", "url", "content"}}
                )
                search_hits.append(hit)

            return search_hits

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    @classmethod
    def clear_instance(cls):
        if cls._instance:
            cls._instance = None
            cls._is_initialized = False
            gc.collect()
            logger.info("Retriever cleared.")
