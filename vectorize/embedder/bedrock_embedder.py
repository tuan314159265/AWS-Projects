"""
AWS Bedrock embedding module.

This module provides the implementation for generating embeddings
using Amazon Bedrock's models via Bearer Token or Default Credentials.
"""

from __future__ import annotations

import os
import json
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from utils.config import get_settings
from utils.logger import get_logger
from ..schemas import Chunk

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
        self._aws_config = settings.aws_config
        self._bedrock_config = settings.bedrock
        self._embedding_config = settings.embedding
        
        self._client = self._create_client()

    def _create_client(self) -> Any:
        """
        Create and return the boto3 Bedrock Runtime client.
        """
        client_kwargs: dict[str, str] = {"service_name": "bedrock-runtime"}
        client_kwargs["region_name"] = self._bedrock_config.region

        # Check authentication mode based on your BedrockConfig properties
        if self._bedrock_config.auth_mode == "api_key" and self._bedrock_config.api_key:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = self._bedrock_config.api_key
            logger.info("[EMBEDDING] Configured AWS_BEARER_TOKEN_BEDROCK for Bedrock API Auth.")
        elif self._bedrock_config.auth_mode == "auto":
            logger.info("[EMBEDDING] Using auto auth mode (AWS Default Credentials).")
        else:
            logger.warning("[EMBEDDING] Auth mode is not explicit. Falling back to default AWS handling.")

        try:
            return boto3.client(**client_kwargs)
        except BotoCoreError:
            logger.exception("[EMBEDDING] Failed to initialize AWS Bedrock client.")
            raise

    def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Generate embeddings for a list of chunks using Bedrock.
        """
        if not chunks:
            return []

        logger.info("[EMBEDDING] Generating embeddings for %d chunks.", len(chunks))

        for chunk in chunks:
            if not chunk.content or not chunk.content.strip():
                continue
                
            chunk.embedding = self._invoke_with_retry(chunk.content)

        return chunks

    def _invoke_with_retry(self, text: str) -> list[float]:
        """
        Invoke the Bedrock API with exponential backoff.
        """
        payload = {
            "inputText": text,
            "dimensions": self._embed_config.dimension,
            "normalize": True
        }
        
        request_body = json.dumps(payload)

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self._client.invoke_model(
                    modelId=self._model_id,
                    body=request_body,
                    accept="application/json",
                    contentType="application/json"
                )
                
                response_data = json.loads(response.get("body").read())
                return response_data.get("embedding", [])
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                
                if error_code == "ThrottlingException" and attempt < self.MAX_RETRIES:
                    sleep_time = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning("[EMBEDDING] Rate limit hit. Retrying in %ds...", sleep_time)
                    time.sleep(sleep_time)
                    continue
                
                logger.exception("[EMBEDDING] Bedrock API Error: %s", error_code)
                raise
            except (json.JSONDecodeError, KeyError):
                logger.exception("[EMBEDDING] Failed to parse JSON response.")
                raise RuntimeError("Invalid response format from AWS Bedrock.") from None
                
        raise RuntimeError("Failed to generate embedding after max retries.")
    
    
