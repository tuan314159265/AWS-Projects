import time
from typing import List

from .retriever import Retriever
from .generator import GeneratorRegistry
from .schemas import SearchHit, GeneratorResponse
from ..utils.logger import get_logger
from ..utils.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class Pipeline:
    def __init__(self):
        self.retriever = Retriever()
        self.generator_registry = GeneratorRegistry()

    def ask(self, query: str, model: str = None) -> GeneratorResponse:
        logger.info(f"Pipeline: query='{query}', model={model or 'default'}")

        try:
            start_time = time.time()
            sources: List[SearchHit] = self.retriever.search(query)

            if not sources:
                return GeneratorResponse(
                    query=query,
                    summary="Không tìm thấy nguồn tin nào liên quan đến câu hỏi của bạn.",
                    results=[], total=0,
                    duration_ms=(time.time() - start_time) * 1000
                )

            answer = self.generator_registry.generate_with_fallback(
                query=query,
                search_hits=sources,
                identifier=model or "default"
            )

            duration_ms = (time.time() - start_time) * 1000

            return GeneratorResponse(
                query=query, summary=answer, results=sources,
                total=len(sources), duration_ms=round(duration_ms, 2)
            )
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            return GeneratorResponse(
                query=query,
                summary="Xin lỗi, hệ thống hiện tại đang gặp sự cố. Vui lòng thử lại sau.",
                results=[], total=0, duration_ms=0.0
            )

    def generate_response(self, query: str, model: str = "default") -> GeneratorResponse:
        return self.ask(query, model=model)
