import time
from .retriever import Retriever
from .generator import generator_registry
from .schemas import SearchHit, GeneratorResponse
from .logger_setup import logger
from typing import List
from .config import settings


class Pipeline:
    def __init__(self):
        self.settings = settings

    def ask(self, query: str, model: str = None, is_vanilla: bool = False) -> GeneratorResponse:
        if not model:
            generator = generator_registry.get_generator("default")
        else:
            generator = generator_registry.get_generator(model)

        logger.info(f"Pipeline: query='{query}', model={model or 'default'}")

        try:
            start_time = time.time()
            retriever = Retriever()
            sources: List[SearchHit] = retriever.search(query)

            if not sources:
                return GeneratorResponse(
                    query=query,
                    summary="Khong tim thay nguon tin lien quan.",
                    results=[], total=0,
                    duration_ms=(time.time() - start_time) * 1000
                )

            answer = generator.generate(query, sources, is_vanilla=is_vanilla)
            duration_ms = (time.time() - start_time) * 1000
            return GeneratorResponse(
                query=query, summary=answer, results=sources,
                total=len(sources), duration_ms=round(duration_ms, 2)
            )
        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            return GeneratorResponse(
                query=query,
                summary="He thong AI dang gap su co. Vui long thu lai.",
                results=[], total=0, duration_ms=0.0
            )

    def generate_response(self, query: str, model: str = "default") -> GeneratorResponse:
        return self.ask(query, model=model)
