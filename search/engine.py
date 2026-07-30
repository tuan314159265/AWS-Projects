import time, json
from typing import List

from .retriever import Retriever
from .generator import GeneratorRegistry
from .schemas import SearchHit, GeneratorResponse
from utils.logger import get_logger
from utils.config import get_settings

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

    def stream_answer(self, query: str, model: str = None):
        """Async generator yielding SSE events."""
        logger.info(f"Pipeline stream: query='{query}', model={model or 'default'}")
        try:
            sources = self.retriever.search(query)
            if not sources:
                yield "event: error\ndata: Không tìm thấy nguồn tin nào\n\n"
                return

            yield "event: metadata\ndata: " + json.dumps({"total": len(sources)}) + "\n\n"

            response_stream = self.generator_registry.generate_with_fallback_stream(
                query=query, search_hits=sources, identifier=model or "default"
            )

            for token in response_stream:
                if token:
                    escaped = token.replace("\n", "\\n").replace("\r", "\\r")
                    yield f"data: {escaped}\n\n"

            yield "event: done\ndata: [DONE]\n\n"
        except Exception as e:
            logger.exception(f"Pipeline stream failed: {e}")
            yield f"event: error\ndata: {e}\n\n"

    def generate_response(self, query: str, model: str = "default") -> GeneratorResponse:
        return self.ask(query, model=model)
