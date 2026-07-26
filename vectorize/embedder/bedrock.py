"""
AWS Bedrock embedding module.

This module provides the implementation for generating embeddings
using Amazon Bedrock's models via standard AWS Credentials.
"""

from __future__ import annotations
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError
from langchain_aws import BedrockEmbeddings

from utils.config import get_settings
from utils.logger import get_logger
from ..schemas import Chunk

# Kế thừa interface
from .base import BaseEmbedder

logger = get_logger(__name__)
settings = get_settings()


class BedrockEmbedder(BaseEmbedder):
    """
    Bedrock embedder strategy supporting both API Key and Auto credentials.
    """
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 2

    def __init__(self) -> None:
        """Initialize the Bedrock client and model configuration."""
        self._embed_config = settings.embedding
        self._bedrock_credentials = settings.aws_config.profiles.get("bedrock", settings.aws_config.profiles.get("default"))
        
        self._client = self._create_client()
        self._model = self._create_model()

    def _create_client(self) -> Any:
        """
        Create and return the boto3 Bedrock Runtime client.
        """
        region = (
            self._bedrock_credentials.region
            if self._bedrock_credentials
            else settings.bedrock.region
        )
        client_kwargs: dict[str, Any] = {
            "service_name": "bedrock-runtime",
            "region_name": region,
            "config": Config(retries={"max_attempts": self.MAX_RETRIES}),
        }

        if self._bedrock_credentials:
            logger.info("[EMBEDDING] Using explicit AWS Profile.")
            
            client_kwargs["aws_access_key_id"] = self._bedrock_credentials.access_key_id
            client_kwargs["aws_secret_access_key"] = self._bedrock_credentials.secret_access_key
            
            if self._bedrock_credentials.session_token:
                client_kwargs["aws_session_token"] = self._bedrock_credentials.session_token
                
            if self._bedrock_credentials.region:
                client_kwargs["region_name"] = self._bedrock_credentials.region
        else:
            logger.warning("[EMBEDDING] No explicit profiles found. Falling back to default boto3 behavior.")

        try:
            return boto3.client(**client_kwargs)
        except BotoCoreError:
            logger.exception("[EMBEDDING] Failed to initialize AWS Bedrock client.")
            raise

    def _create_model(self):
        """
        Create and return the Bedrock embedding model instance.
        """
        try:
            return BedrockEmbeddings(
                model_id=self._embed_config.model_id,
                client=self._client,
                region_name=(
                    self._bedrock_credentials.region
                    if self._bedrock_credentials
                    else settings.bedrock.region
                ),
                dimensions=self._embed_config.dimension,
                normalize=True,
            )
        except Exception as e:
            logger.exception(f"[EMBEDDING] Failed to initialize Bedrock embedding model: {e}")
            raise

    def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Generate embeddings for a batch of chunks.
        """
        if not chunks:
            return []

        logger.info("[EMBEDDING] Generating embeddings for %d chunks.", len(chunks))

        try:
            # Remove any chunks that are empty or contain only whitespace
            valid_chunks = [c for c in chunks if c.content and c.content.strip()]
            texts = [chunk.content for chunk in valid_chunks]
            
            if not texts:
                return chunks

            # Generate embeddings using the Bedrock embedding model
            embeddings = self._model.embed_documents(texts)
            
            # Assign embeddings back to the corresponding chunks
            for chunk, vector in zip(valid_chunks, embeddings):
                chunk.embedding = vector

            return chunks
        except Exception as e:
            logger.exception(
                "[EMBEDDING] Failed to generate embeddings due to an error: %s",
                e,
            )
            raise RuntimeError("Embedding generation failed.") from e

    def embed_query(self, query: str) -> list[float]:
        """
        Generate an embedding for a single query string.
        """
        if not query or not query.strip():
            logger.warning("[EMBEDDING] Received an empty or whitespace-only query.")
            return []

        try:
            logger.info("[EMBEDDING] Generating embedding for query: %s", query)
            embedding = self._model.embed_query(query)
            return embedding
        except Exception as e:
            logger.exception(f"[EMBEDDING] Failed to generate embedding for query due to an error: {e}")
            raise RuntimeError("Query embedding generation failed.")
        


    
