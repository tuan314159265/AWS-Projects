"""
Vectorization Service.

This module orchestrates the ETL pipeline: 
Warehouse (Extract) -> Bedrock (Transform) -> pgvector (Load).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from utils.logger import get_logger
from vectorize.embedder.base import BaseEmbedder
from vectorize.embedder.bedrock import BedrockEmbedder
from vectorize.repository.warehouse_repository import WarehouseRepository
from vectorize.repository.vector_repository import VectorRepository
from vectorize.schemas import VectorRecord
from .schemas import Chunk, VectorRecord

logger = get_logger(__name__)

class BaseVectorizeService(ABC):
    """
    Abstract base class for vectorization services.
    """

    @abstractmethod
    def process_single_article(self, article_id: int) -> None:
        """
        Process a single article through the vectorization pipeline.

        Parameters
        ----------
        article_id : str
            The unique identifier of the article to be processed.
        """
        pass

    @abstractmethod
    def process_batch(self, batch_size: int | None = None) -> None:
        """
        Process a batch of articles through the vectorization pipeline.

        Parameters
        ----------
        batch_size : int, optional
            The number of articles to process in each batch, by default 500
        """
        pass

class VectorizeService(BaseVectorizeService):
    """
    Application service orchestrating the chunk vectorization process.
    """

    def __init__(self,
                 warehouse_repository: WarehouseRepository,
                 embedder: BaseEmbedder,
                 vector_store: VectorRepository
                 ) -> None:
        """
        Initialize the service and components.
        """
        logger.info("[EMBEDDING] Initializing VectorizeService...")
        self._warehouse_repo = warehouse_repository
        self._embedder = embedder
        self._vector_store = vector_store
        logger.info("[EMBEDDING] Initialization complete.")


    def process_single_article(self, article_id: int) -> int:
        """
        Execute the End-to-End vectorization pipeline for a single article.
        """
        logger.info("[EMBEDDING] Starting vectorization for article: %s", article_id)

        try:

            chunks = self._warehouse_repo.fetch_chunks_by_article(article_id)
            
            if not chunks:
                logger.warning("[EMBEDDING] No chunks found for article: %s. Skipping.", article_id)
                return 0

            embedded_chunks = self._embedder.embed(chunks)

            if not embedded_chunks:
                logger.error("[EMBEDDING] Failed to generate embeddings for: %s.", article_id)
                return 0

            vector_records = [
                VectorRecord(
                    article_id=chunk.article_id,
                    chunk_index=chunk.chunk_index,
                    embedding=chunk.embedding
                )
                for chunk in embedded_chunks if chunk.ready
            ]

            if not vector_records:
                logger.info("[EMBEDDING] No valid records to save for article: %d", article_id)
                return 0
            
            self._vector_store.upsert_vectors(vector_records)
            num_vectors = len(vector_records)
            logger.info("[EMBEDDING] Successfully upserted %d vectors for article: %s", 
                        num_vectors, article_id)
            return num_vectors

        except Exception as e:
            logger.exception(f"[EMBEDDING] Critical failure for article: {article_id} due to {e}.")
            raise

    def process_batch(self, batch_size: int | None = None) -> int:
        """
        Process a batch of articles.
        """
        logger.info("[EMBEDDING] Processing articles from warehouse...")
        total_vectors = 0

        chunks: list[Chunk] = self._warehouse_repo.fetch_chunks(limit=batch_size)

        if not chunks:
            logger.info("[EMBEDDING] No chunks found in the warehouse. Batch processing complete.")
            return 0
        
        try:
            embedded_chunks = self._embedder.embed(chunks)
        except Exception:
            logger.error("[EMBEDDING] Failed to generate embeddings for the batch.")
            raise

        vector_records: list[VectorRecord] = [
            VectorRecord(
                article_id=chunk.article_id,
                chunk_index=chunk.chunk_index,
                embedding=chunk.embedding
            )
            for chunk in embedded_chunks if chunk.ready
        ]
        if not vector_records:
            logger.warning("[EMBEDDING] No valid vector records generated from the batch.")
            return 0
        
        try:
            self._vector_store.upsert_vectors(vector_records)
            total_vectors = len(vector_records)
            logger.info("[EMBEDDING] Successfully upserted %d vectors from the batch.", total_vectors)
            return total_vectors
        except Exception as e:
            logger.error(f"[EMBEDDING] Failed to upsert vector records into the vector store due to {e}.")
            raise
    
    def process_batch_by_article_ids(self, article_ids: list[int]) -> int:
        """
        Process a batch of articles by their IDs.
        """
        logger.info("[EMBEDDING] Processing batch of articles by IDs: %s", article_ids)
        try:
            total_vectors = 0
            for article_id in article_ids:
                vectors_count = self.process_single_article(article_id)
                total_vectors += vectors_count
            logger.info("[EMBEDDING] Successfully processed %d articles with a total of %d vectors.", 
                        len(article_ids), total_vectors)
            return total_vectors
        except Exception:
            logger.exception("[EMBEDDING] Critical failure while processing batch of articles.")
            raise