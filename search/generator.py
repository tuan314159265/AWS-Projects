from __future__ import annotations

import re
import time
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from langchain_aws import ChatBedrockConverse
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_ollama.chat_models import ChatOllama

from utils.config import LLMProviderConfig, get_settings
from utils.logger import get_logger
from .prompts import NEWS_RAG_HUMAN_PROMPT, NEWS_RAG_SYSTEM_PROMPT
from .schemas import SearchHit

settings = get_settings()
logger = get_logger(__name__)

class BaseGenerator(ABC):
    def __init__(self, config: LLMProviderConfig = None):
        """
        Initialize the base generator with a specific provider configuration.
        """
        try:
            if not config:
                raise ValueError("config is required")
            
            self._config = config
            self._llm = self._init_llm()

            self._prompt_template = ChatPromptTemplate.from_messages([
                ("system", NEWS_RAG_SYSTEM_PROMPT),
                ("human", NEWS_RAG_HUMAN_PROMPT)
            ])
            self._chain = self._prompt_template | self._llm | StrOutputParser()

        except Exception as e:
            logger.error(f"[GENERATOR] BaseGenerator init failed: {e}")
            raise

    @abstractmethod
    def _init_llm(self):
        """Optional method to set up LLM and prompt chain, can be overridden by subclasses."""
        pass

    def _format_context(self, sources: List[SearchHit]) -> str:
        """
        Format the retrieved search hits into a single context string.
        Included publish date to help LLM understand chronological context.
        """
        formatted_chunks = []
        for i, s in enumerate(sources):
            pub_ts = s.metadata.get("publish_timestamp")
            
            if pub_ts and pub_ts > 0:
                pub_date = datetime.fromtimestamp(pub_ts).strftime('%d/%m/%Y')
            else:
                pub_date = "Không rõ"

            chunk_text = (
                f"Tài liệu [{i+1}]\n"
                f"Tiêu đề: {s.title}\n"
                f"Ngày đăng: {pub_date}\n" 
                f"URL: {s.url}\n"
                f"Nội dung: {s.content}"
            )
            formatted_chunks.append(chunk_text)
            
        return "\n\n".join(formatted_chunks)

    def _clean_response(self, text: str) -> str:
        """
        Clean up the LLM response, e.g., removing internal reasoning tags like <think>.
        """
        if text:
            return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text

    def generate(self, query: str, search_hits: List[SearchHit]) -> str:
        """
        Generate an answer using the configured LLM and the provided search hits.
        """
        try:
            if not search_hits:
                return "Không tìm thấy nguồn tin nào liên quan."

            context = self._format_context(search_hits)
            answer = self._chain.invoke({"context": context, "question": query})

            return self._clean_response(answer)
        except Exception as e:
            logger.error(f"Generate error ({self._config.name}): {e}")
            raise

    def cleanup(self):
        """Release resources associated with the generator."""
        self._llm = None
        self._chain = None


class GroqGenerator(BaseGenerator):
    def _init_llm(self):
        return ChatGroq(
            model=self._config.model_id,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            groq_api_key=self._config.api_key
        )

# class GoogleGenerator(BaseGenerator):
#     def _init_llm(self):
#         return ChatGoogleGenerativeAI(
#             model=self._config.model_id,
#             temperature=self._config.temperature,
#             max_output_tokens=self._config.max_tokens,
#             google_api_key=self._config.api_key,
#         )

class OllamaGenerator(BaseGenerator):
    def _init_llm(self):
        return ChatOllama(
            model=self._config.model_id,
            temperature=self._config.temperature,
            base_url=self._config.base_url or "http://localhost:11434"
        )


class BedrockGenerator(BaseGenerator):
    def _init_llm(self):
        self._aws_creds = settings.aws_config.profiles.get("bedrock",
                                                           settings.aws_config.profiles.get("default", None))
        return ChatBedrockConverse(
            model_id=self._config.model_id,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            region_name=self._aws_creds.region if self._aws_creds else None,
            aws_access_key_id=self._aws_creds.access_key_id if self._aws_creds else None,
            aws_secret_access_key=self._aws_creds.secret_access_key if self._aws_creds else None,
            aws_session_token=self._aws_creds.session_token if self._aws_creds else None
        )


class GeneratorRegistry:
    _instances = None
    _lock = threading.Lock()
    _is_initialized = False

    _PROVIDER_MAP: Dict[str, Type[BaseGenerator]] = {
        # "google": GoogleGenerator,
        "groq": GroqGenerator,
        "ollama": OllamaGenerator,
        "bedrock": BedrockGenerator
    }

    def __new__(cls):
        if cls._instances is None:
            with cls._lock:
                if cls._instances is None:
                    cls._instances = super().__new__(cls)
                    cls._instances._is_initialized = False
        return cls._instances

    def __init__(self):
        if self._is_initialized:
            return
        with self._lock:
            if not self._is_initialized:
                self._generators: Dict[str, BaseGenerator] = {}
                self._id_map: Dict[str, str] = {}
                self._setup()
                self._is_initialized = True

    def _setup(self):
        """Instantiate and register all configured providers."""
        self._id_map: Dict[str, str] = {}
        for cfg in settings.llm.providers:
            provider_class = self._PROVIDER_MAP.get(cfg.provider.lower())
            if provider_class:
                try:
                    gen = provider_class(cfg)
                    self._generators[cfg.name] = gen
                    self._id_map[cfg.model_id] = cfg.name
                    logger.info(f"[GENERATOR] Registered generator: {cfg.name} (Provider: {cfg.provider}, Model ID: {cfg.model_id})")
                except Exception as e:
                    logger.error(f"[GENERATOR] Error occurred while initializing {cfg.name}: {e}")
            else:
                logger.warning(f"[GENERATOR] Skipping unsupported provider: {cfg.provider}")

    def get_generator(self, identifier='default') -> BaseGenerator:
        """
        Get a specific generator by its name or model ID.
        """
        if not self._generators:
            raise ValueError("[GENERATOR] No generators registered.")
        if not identifier or identifier == "default":
            first_name = next(iter(self._generators))
            return self._generators[first_name]
        if identifier in self._generators:
            return self._generators[identifier]
        name = self._id_map.get(identifier)
        if name:
            return self._generators[name]
        raise ValueError(f"[GENERATOR] Generator '{identifier}' not found.")

    def _resolve_name(self, identifier='default') -> str:
        if not self._generators:
            raise ValueError("[GENERATOR] No generators registered.")
        if not identifier or identifier == "default":
            return next(iter(self._generators))
        if identifier in self._generators:
            return identifier
        name = self._id_map.get(identifier)
        if name:
            return name
        raise ValueError(f"[GENERATOR] Generator '{identifier}' not found.")

    def generate_with_fallback(self, query: str, search_hits: List[SearchHit],
                               identifier: str = 'default',
                               fallback_identifiers: List[str] = None) -> str:
        """
        Attempt to generate an answer with a primary generator, falling back
        to other generators if the primary one fails.
        """
        if not search_hits:
            return "Không tìm thấy nguồn tin nào liên quan."

        primary_name = None
        try:
            primary_name = self._resolve_name(identifier)
            gen = self._generators[primary_name]
            return gen.generate(query, search_hits)
        except Exception as e:
            logger.error(f"[GENERATOR] Error occurred while generating with primary generator '{primary_name}': {e}")

        if fallback_identifiers is None:
            fallback_identifiers = list(self._generators.keys())

        for fallback_id in fallback_identifiers:
            try:
                fallback_name = self._resolve_name(fallback_id)
                if fallback_name == primary_name:
                    continue
                logger.info(f"[GENERATOR] Trying fallback: {fallback_id}")
                gen = self._generators[fallback_name]
                return gen.generate(query, search_hits)
            except Exception as e:
                logger.error(f"[GENERATOR] Error occurred while generating with fallback generator '{fallback_id}': {e}")
                continue

        return "Xin lỗi, hệ thống hiện đang gặp sự cố. Vui lòng thử lại sau."

    def list_generators(self) -> List[Dict[str, str]]:
        results = []
        for name, gen in self._generators.items():
            model_id = next((mid for mid, n in self._id_map.items() if n == name), "N/A")
            results.append({"name": name, "model_id": model_id, "provider": gen._config.provider})
        return results

generator_registry = GeneratorRegistry()
