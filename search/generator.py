from abc import ABC, abstractmethod
from typing import List, Type, Dict
from .logger_setup import logger
import threading
import re

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama.chat_models import ChatOllama
from langchain_groq import ChatGroq

from .config import settings, LLMInstanceConfig
from .schemas import SearchHit
from .prompts import (
    NEWS_RAG_SYSTEM_PROMPT, NEWS_RAG_HUMAN_PROMPT,
    VANILLA_SYSTEM_PROMPT, VANILLA_HUMAN_PROMPT
)


class BaseGenerator(ABC):
    def __init__(self, config: LLMInstanceConfig = None):
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

            self._vanilla_prompt = ChatPromptTemplate.from_messages([
                ("system", VANILLA_SYSTEM_PROMPT),
                ("human", VANILLA_HUMAN_PROMPT)
            ])
            self._vanilla_chain = self._vanilla_prompt | self._llm | StrOutputParser()
        except Exception as e:
            logger.error(f"BaseGenerator init failed: {e}")
            raise

    @abstractmethod
    def _init_llm(self):
        pass

    def _format_context(self, sources: List[SearchHit]) -> str:
        return "\n\n".join([
            f"[{i+1}] {s.title}: {s.content}\nSource: {s.url}"
            for i, s in enumerate(sources)
        ])

    def _clean_response(self, text: str) -> str:
        if text:
            return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        return text

    def generate(self, query: str, search_hits: List[SearchHit], is_vanilla: bool = False) -> str:
        try:
            if not search_hits:
                return "Không tìm thấy nguồn tin nào liên quan."

            context = self._format_context(search_hits)
            chain = self._vanilla_chain if is_vanilla else self._chain
            answer = chain.invoke({"context": context, "question": query})
            return self._clean_response(answer)
        except Exception as e:
            logger.error(f"Generate error ({self._config.name}): {e}")
            raise

    def cleanup(self):
        self._llm = None
        self._chain = None
        self._vanilla_chain = None


class GroqGenerator(BaseGenerator):
    def _init_llm(self):
        return ChatGroq(
            model=self._config.model_id,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            api_key=self._config.api_key
        )


class GoogleGenerator(BaseGenerator):
    def _init_llm(self):
        return ChatGoogleGenerativeAI(
            model=self._config.model_id,
            temperature=self._config.temperature,
            max_output_tokens=self._config.max_tokens,
            google_api_key=self._config.api_key,
        )


class OllamaGenerator(BaseGenerator):
    def _init_llm(self):
        return ChatOllama(
            model=self._config.model_id,
            temperature=self._config.temperature,
            base_url=self._config.base_url or "http://localhost:11434"
        )


class OpenAIGenerator(BaseGenerator):
    def _init_llm(self):
        return ChatOpenAI(
            model=self._config.model_id,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            api_key=self._config.api_key,
            base_url=self._config.base_url
        )


class GeneratorRegistry:
    _instances = None
    _lock = threading.Lock()
    _is_initialized = False

    _PROVIDER_MAP: Dict[str, Type[BaseGenerator]] = {
        "openai": OpenAIGenerator,
        "google": GoogleGenerator,
        "groq": GroqGenerator,
        "ollama": OllamaGenerator,
        "siliconflow": OpenAIGenerator
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
                self._setup()
                self._is_initialized = True

    def _setup(self):
        self._id_map: Dict[str, str] = {}
        for cfg in settings.llm.instances:
            provider_class = self._PROVIDER_MAP.get(cfg.provider.lower())
            if provider_class:
                try:
                    gen = provider_class(cfg)
                    self._generators[cfg.name] = gen
                    self._id_map[cfg.model_id] = cfg.name
                    logger.info(f"Đã đăng ký: {cfg.name} ({cfg.model_id}) qua {cfg.provider}")
                except Exception as e:
                    logger.error(f"Lỗi khởi tạo {cfg.name}: {e}")

    def get_generator(self, identifier='default') -> BaseGenerator:
        if not self._generators:
            raise ValueError("Không có generator nào được đăng ký.")
        if identifier in self._generators:
            return self._generators[identifier]
        name = self._id_map.get(identifier)
        if name:
            return self._generators[name]
        raise ValueError(f"Không tìm thấy generator '{identifier}'.")

    def generate_with_fallback(self, query: str, search_hits: List[SearchHit],
                               identifier: str = 'default', fallback_identifiers: List[str] = None,
                               is_vanilla: bool = False) -> str:
        if not search_hits:
            return "Không tìm thấy nguồn tin nào liên quan."

        try:
            gen = self.get_generator(identifier)
            return gen.generate(query, search_hits, is_vanilla)
        except Exception as e:
            logger.error(f"Generator chính gặp lỗi: {e}")

        if fallback_identifiers is None:
            fallback_identifiers = list(self._generators.keys())

        for fallback_id in fallback_identifiers:
            if fallback_id == identifier:
                continue
            try:
                logger.info(f"Thử fallback: {fallback_id}")
                gen = self.get_generator(fallback_id)
                return gen.generate(query, search_hits, is_vanilla)
            except Exception:
                continue

        return "Xin lỗi, hệ thống AI hiện đang gặp sự cố."

    def list_generators(self) -> List[Dict[str, str]]:
        results = []
        for name, gen in self._generators.items():
            model_id = next((mid for mid, n in self._id_map.items() if n == name), "N/A")
            results.append({"name": name, "model_id": model_id, "provider": gen._config.provider})
        return results


generator_registry = GeneratorRegistry()
