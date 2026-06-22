import os
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
shared_config = SettingsConfigDict(
    env_file=BASE_DIR / ".env",
    env_file_encoding="utf-8",
    extra="ignore"
)


class ModelConfig(BaseSettings):
    model_config = shared_config
    embedding: str = Field(alias='EMBEDDING_MODEL', default='BAAI/bge-small-en-v1.5')
    embedding_size: int = Field(alias='EMBEDDING_SIZE', default=384)
    top_k: int = Field(alias='TOP_K', default=20)


class LLMInstanceConfig(BaseModel):
    provider: str
    model_id: str
    name: str
    temperature: float = 0.0
    max_tokens: int
    api_key: str = None
    base_url: str = None


class LLMConfig(BaseSettings):
    model_config = shared_config
    default_temperature: float = Field(alias='LLM_TEMPERATURE', default=0.1)
    max_tokens: int = Field(alias='LLM_MAX_TOKENS', default=2048)
    num_models: int = Field(alias='NUM_MODEL_SUPPORT', default=1)
    instances: list[LLMInstanceConfig] = []

    @model_validator(mode='after')
    def populate_instances(self) -> 'LLMConfig':
        temp_instances = []
        for i in range(1, self.num_models + 1):
            name = os.getenv(f'MODEL_{i}_NAME')
            provider = os.getenv(f'MODEL_{i}_PROVIDER', '').strip()
            model_id = os.getenv(f'MODEL_{i}_MODEL_ID', '').strip()
            api_key = os.getenv(f'MODEL_{i}_API_KEY', '').strip() or None
            base_url = os.getenv(f'MODEL_{i}_BASE_URL', '') or None

            raw_temp = os.getenv(f'MODEL_{i}_TEMPERATURE')
            temp = float(raw_temp) if raw_temp else self.default_temperature
            max_tokens = int(os.getenv(f'MODEL_{i}_MAX_TOKENS', self.max_tokens))

            if name and provider and model_id:
                instance = LLMInstanceConfig(
                    name=name, provider=provider.lower(), model_id=model_id,
                    api_key=api_key, base_url=base_url,
                    temperature=temp, max_tokens=max_tokens
                )
                temp_instances.append(instance)

        self.instances = temp_instances
        return self


class SearchConfig(BaseSettings):
    model_config = shared_config
    host: str = Field(alias='QDRANT_HOST', default='localhost')
    port: int = Field(alias='QDRANT_PORT', default=6333)
    api_key: str = Field(alias='QDRANT_API_KEY', default='')
    grpc_port: int = Field(alias='QDRANT_GRPC_PORT', default=6334)
    collection_name: str = Field(alias='QDRANT_COLLECTION_NAME', default='news_chunks')

    @property
    def qdrant_url(self) -> str:
        protocol = "https" if ".cloud.qdrant.io" in self.host else "http"
        return f"{protocol}://{self.host}"


class Settings(BaseSettings):
    model_config = shared_config
    search: SearchConfig = SearchConfig()
    model: ModelConfig = ModelConfig()
    llm: LLMConfig = LLMConfig()


settings = Settings()
