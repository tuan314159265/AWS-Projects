"""
Retriever Module.

This module provides the retrieval engine for the RAG pipeline. It handles
the transformation of user queries into vector embeddings and fetches the
most semantically similar documents from the vector store.
"""
from __future__ import annotations
from typing import List

from utils.logger import get_logger
from vectorize.embedder.bedrock import BedrockEmbedder
from vectorize.repository.vector_repository import VectorRepository
from .schemas import SearchHit
from utils.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class Retriever:
    """
    Retriever class for the RAG FastAPI backend.
    """

    def __init__(
        self
    ) -> None:
        logger.info("[RETRIEVER] Initializing RetrievalService...")
        self._embedder = BedrockEmbedder()
        self._vector_store = VectorRepository()
        self._top_k = settings.retrieval.top_k


    def search(self, query: str) -> List[SearchHit]:
        "Perform a semantic search based on the user's query."
        try:
            logger.info(f"[RETRIEVER] Searching results for query: {query}")
            query_embedding = self._embedder.embed_query(query=query)

            raw_results = self._vector_store.search_vectors(query_embedding=query_embedding, 
                                                            top_k=self._top_k)

            search_hits: List[SearchHit] = []
            for chunk, distance in raw_results:
                similarity_score = 1.0 - distance
        
                hit = SearchHit(
                    id=f"{chunk.article_id}_{chunk.chunk_index}",
                    title=chunk.title,
                    content=chunk.content,
                    url=chunk.url,
                    score=similarity_score,
                    metadata={
                        "authors": chunk.authors,
                        "publish_timestamp": chunk.publish_timestamp,
                        "distance": distance
                    }
                )
                search_hits.append(hit)

            return search_hits

        except Exception as e:
            logger.error(f"[RETRIEVER] Search failed: {e}")
            return []
