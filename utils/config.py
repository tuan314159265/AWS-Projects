"""
Application configuration.

This module centralizes all application settings using Pydantic Settings.
Configuration values are loaded from environment variables or a .env file.

The module exposes a singleton Settings instance via ``get_settings()``.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import os
from dotenv import load_dotenv



# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

SHARED_CONFIG = SettingsConfigDict(
    env_file=PROJECT_ROOT / ".env",
    env_file_encoding="utf-8",
    extra="ignore",
)

# ============================================================================
# AWS Configuration
# ============================================================================
class AWSProfileConfig(BaseModel):
    """Store AWS profile configuration."""
    name: str
    access_key_id: str
    secret_access_key: str
    region: str
    session_token: str | None = None  

class AWSConfig(BaseSettings):
    """Store AWS configuration."""
    model_config = SHARED_CONFIG

    profile_num: int = Field(alias="PROFILE_NUM", default=0)
    profiles: dict[str, AWSProfileConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def load_aws_profiles(self) -> "AWSConfig":
        """Load AWS profiles from environment variables."""
        profiles = {}
        
        for idx in range(1, self.profile_num + 1):
            prefix = f"{idx}_"
            
            profile_name = os.getenv(prefix + "PROFILE_NAME")
            if not profile_name:
                continue

            profiles[profile_name] = AWSProfileConfig(
                name=profile_name,
                access_key_id=os.getenv(prefix + "ACCESS_KEY_ID", ""),
                secret_access_key=os.getenv(prefix + "SECRET_ACCESS_KEY", ""),
                region=os.getenv(prefix + "REGION", "ap-southeast-1"),
                session_token=os.getenv(prefix + "SESSION_TOKEN") 
            )

        self.profiles = profiles
        return self

# ============================================================================
# Database
# ============================================================================

class DatabaseConfig(BaseSettings):
    """Database configuration."""
    model_config = SHARED_CONFIG

    host: str = Field(alias="DB_HOST", default="localhost")
    port: int = Field(alias="DB_PORT", default=5432)
    database: str = Field(alias="DB_NAME", default="warehouse")
    username: str = Field(alias="DB_USER", default="postgres")
    password: str = Field(alias="DB_PASSWORD", default="")

    @property
    def url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

# ============================================================================
# Vector Store
# ============================================================================

class VectorStoreConfig(BaseSettings):
    """Vector database configuration."""

    model_config = SHARED_CONFIG

    provider: Literal["qdrant", "pgvector"] = Field(
        alias="VECTOR_PROVIDER",
        default="qdrant",
    )

    host: str | None = Field(alias="VECTOR_HOST", default=None)

    @model_validator(mode="after")
    def fallback_host(self) -> "VectorStoreConfig":
        if self.provider == "pgvector" and not self.host:
            self.host = os.getenv("DB_HOST", "localhost")
        return self

    port: int = Field(alias="VECTOR_PORT", default=6333)

    grpc_port: int = Field(
        alias="VECTOR_GRPC_PORT",
        default=6334,
    )

    api_key: str | None = Field(
        alias="VECTOR_API_KEY",
        default=None,
    )

    collection_name: str = Field(
        alias="VECTOR_COLLECTION",
        default="news_chunks",
    )

    vector_name: str | None = Field(
        alias="VECTOR_NAME",
        default=None,
    )

    embedding_dimension: int = Field(
        alias="EMBEDDING_DIMENSION",
        default=1024,
    )

    @property
    def url(self) -> str:
        """Return vector database endpoint."""

        protocol = (
            "https"
            if ".cloud.qdrant.io" in self.host
            else "http"
        )

        return f"{protocol}://{self.host}"


# =============================================================================
# Retrieval
# =============================================================================


class RetrievalConfig(BaseSettings):
    """Retrieval configuration."""

    model_config = SHARED_CONFIG

    top_k: int = Field(
        alias="TOP_K",
        default=20,
    )

    similarity_threshold: float = Field(
        alias="SIMILARITY_THRESHOLD",
        default=0.75,
    )

    enable_reranker: bool = Field(
        alias="ENABLE_RERANKER",
        default=False,
    )

    rerank_top_k: int = Field(
        alias="RERANK_TOP_K",
        default=5,
    )

# =============================================================================
# Bedrock Configuration
# =============================================================================
class BedrockConfig(BaseSettings):
    """
    Shared Bedrock configuration.
    """

    model_config = SHARED_CONFIG

    auth_mode: Literal[
        "auto",
        "api_key",
    ] = Field(
        alias="BEDROCK_AUTH_MODE",
        default="auto",
    )

    api_key: str | None = Field(
        alias="BEDROCK_API_KEY",
        default=None,
    )

    region: str = Field(
        alias="BEDROCK_REGION",
        default="ap-southeast-1",
    )

    @property
    def use_api_key(self) -> bool:
        return (
            self.auth_mode == "api_key"
            and bool(self.api_key)
        )

    @property
    def use_default_credentials(self) -> bool:
        return self.auth_mode == "auto"

# =============================================================================
# Embedding Model
# =============================================================================

class EmbeddingConfig(BaseSettings):
    """
    Embedding configuration.
    """

    model_config = SHARED_CONFIG

    provider: Literal[
        "bedrock",
    ] = Field(
        alias="EMBEDDING_PROVIDER",
        default="bedrock",
    )

    model_id: str = Field(
        alias="EMBEDDING_MODEL_ID",
        default="amazon.titan-embed-text-v2:0",
    )

    dimension: int = Field(
        alias="EMBEDDING_DIMENSION",
        default=1024,
    )

#=============================================================================
# LLM Provider Configuration
#=============================================================================
class LLMProviderConfig(BaseModel):
    """
    LLM provider configuration.
    """

    name: str

    provider: Literal[
        "bedrock",
        "groq",
        "openai",
        "gemini",
        "ollama",
        "azure_openai",
    ]

    model_id: str

    temperature: float = 0.1

    max_tokens: int = 2048

    api_key: str | None = None

    base_url: str | None = None

    region: str | None = None

    enabled: bool = True

    @property
    def is_available(self) -> bool:

        if not self.enabled:
            return False

        if self.provider == "bedrock":
            return True

        return bool(self.api_key)
    
class LLMConfig(BaseSettings):
    """
    LLM configuration with fallback support.
    """

    model_config = SHARED_CONFIG

    count: int = Field(
        alias="LLM_COUNT",
        default=1,
    )

    providers: list[LLMProviderConfig] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def load_providers(self) -> "LLMConfig":

        import os

        providers = []

        for idx in range(1, self.count + 1):

            prefix = f"LLM_{idx}_"

            provider_name = os.getenv(
                prefix + "PROVIDER"
            )

            if not provider_name:
                continue

            providers.append(
                LLMProviderConfig(
                    name=os.getenv(
                        prefix + "NAME",
                        f"LLM-{idx}",
                    ),
                    provider=provider_name.lower(),
                    model_id=os.getenv(
                        prefix + "MODEL_ID",
                    ),
                    api_key=os.getenv(
                        prefix + "API_KEY",
                    ),
                    base_url=os.getenv(
                        prefix + "BASE_URL",
                    ),
                    region=os.getenv(
                        prefix + "REGION",
                    ),
                    temperature=float(
                        os.getenv(
                            prefix + "TEMPERATURE",
                            "0.1",
                        )
                    ),
                    max_tokens=int(
                        os.getenv(
                            prefix + "MAX_TOKENS",
                            "2048",
                        )
                    ),
                    enabled=os.getenv(
                        prefix + "ENABLED",
                        "true",
                    ).lower()
                    == "true",
                )
            )

        self.providers = providers

        return self

    @property
    def fallback_chain(
        self,
    ) -> list[LLMProviderConfig]:

        return [
            provider
            for provider in self.providers
            if provider.is_available
        ]
    
#=============================================================================
# Application Settings
#=============================================================================
class Settings(BaseSettings):
    """
    Application settings.
    """

    model_config = SHARED_CONFIG

    aws_config: AWSConfig = (
        AWSConfig()
    )

    database: DatabaseConfig = (
        DatabaseConfig()
    )

    vector_store: VectorStoreConfig = (
        VectorStoreConfig()
    )

    retrieval: RetrievalConfig = (
        RetrievalConfig()
    )

    bedrock: BedrockConfig = (
        BedrockConfig()
    )

    embedding: EmbeddingConfig = (
        EmbeddingConfig()
    )

    llm: LLMConfig = (
        LLMConfig()
    )

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached settings instance.
    """
    return Settings()

