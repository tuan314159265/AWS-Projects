"""Bedrock document reranking for the search pipeline using Langchain."""

from __future__ import annotations

from typing import Any, Sequence

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from langchain_aws import BedrockRerank
from langchain_core.documents import Document

from utils.config import get_settings
from utils.logger import get_logger
from .schemas import SearchHit

logger = get_logger(__name__)
settings = get_settings()


class RerankerError(RuntimeError):
    """Raised when Bedrock returns an unusable reranking response."""


class BedrockReranker:
    """Rerank search hits with the Amazon Bedrock Agent Runtime API via Langchain."""

    MAX_RETRIES = 3

    def __init__(self, client: Any | None = None) -> None:
        self._config = settings.rerank
        self._credentials = settings.aws_config.profiles.get(
            "bedrock",
            settings.aws_config.profiles.get("default"),
        )
        self._region = (
            getattr(self._config, "region", None)
            or (self._credentials.region if self._credentials else None)
            or settings.bedrock.region
        )
        self._model_id = self._config.model_id
        self._max_document_chars = max(1, self._config.max_document_chars)
        
        # Initialize boto3 client and Langchain model
        self._client = client if client is not None else self._create_client()
        self._model = self._create_model()

    def _create_client(self) -> Any:
        """Create a Bedrock Agent Runtime client using the configured profile."""
        client_kwargs: dict[str, Any] = {
            "service_name": "bedrock-agent-runtime",
            "region_name": self._region,
            "config": Config(retries={"max_attempts": self.MAX_RETRIES}),
        }

        if self._credentials:
            client_kwargs.update(
                {
                    "aws_access_key_id": self._credentials.access_key_id,
                    "aws_secret_access_key": self._credentials.secret_access_key,
                }
            )
            if self._credentials.session_token:
                client_kwargs["aws_session_token"] = self._credentials.session_token

        try:
            return boto3.client(**client_kwargs)
        except (BotoCoreError, ClientError) as exc:
            logger.exception("[RERANKER] Failed to initialize Bedrock client: %s", exc)
            raise RerankerError("Failed to initialize Bedrock reranker") from exc

    def _create_model(self) -> BedrockRerank:
        """Create and return the Langchain BedrockRerank model instance."""
        try:
            return BedrockRerank(
                model_arn=self._model_arn(),
                client=self._client,
                top_n=max(1, self._config.rerank_top_k)
            )
        except Exception as e:
            logger.exception("[RERANKER] Failed to initialize BedrockRerank model: %s", e)
            raise RerankerError("Failed to initialize Langchain BedrockRerank model") from e

    def _model_arn(self) -> str:
        """Convert a Bedrock model ID to the ARN expected by the rerank API."""
        if self._model_id.startswith("arn:"):
            return self._model_id
        return f"arn:aws:bedrock:{self._region}::foundation-model/{self._model_id}"

    def _document_text(self, hit: SearchHit) -> str:
        """Build a bounded text representation of a search hit including metadata."""
        title = (hit.title or "").strip()
        content = (hit.content or "").strip()
        timestamp = (hit.metadata or {}).get("publish_timestamp", "Unknown")
        
        text = (
            f"Title: {title}\nContent: {content}\nTime: {timestamp}"
            if title
            else content
        )
        return text[: self._max_document_chars]

    def rerank(self, query: str, hits: Sequence[SearchHit]) -> list[SearchHit]:
        """Return hits ordered by Bedrock relevance, preserving vector scores."""
        normalized_query = query.strip() if query else ""
        if not normalized_query:
            raise ValueError("Query cannot be empty when reranking")
        if not hits:
            return []

        # Convert SearchHit instances to Langchain Documents
        documents = [
            Document(
                page_content=self._document_text(hit),
                metadata={"original_index": idx}
            )
            for idx, hit in enumerate(hits)
        ]

        try:
            # Langchain handles the underlying API call and response parsing
            compressed_docs = self._model.compress_documents(
                documents=documents,
                query=normalized_query
            )
        except Exception as exc:
            logger.exception("[RERANKER] Bedrock rerank failed via Langchain: %s", exc)
            raise RerankerError("Bedrock rerank failed") from exc

        reranked: list[SearchHit] = []

        # Reconstruct the SearchHit list based on Langchain's ordered output
        for rank, doc in enumerate(compressed_docs, start=1):
            original_index = doc.metadata.get("original_index")
            relevance_score = doc.metadata.get("relevance_score", 0.0)

            if original_index is None or original_index >= len(hits):
                continue

            # Deep copy to avoid mutating the original sequence (Pydantic v2)
            hit = hits[original_index].model_copy(deep=True)
            metadata = dict(hit.metadata or {})
            
            # Update scores and metadata
            metadata["vector_score"] = hit.score
            metadata["rerank_score"] = float(relevance_score)
            metadata["rerank_rank"] = rank
            
            hit.score = float(relevance_score)
            hit.metadata = metadata
            reranked.append(hit)

        if not reranked:
            raise RerankerError("Bedrock returned no valid reranking results")

        return reranked


Reranker = BedrockReranker