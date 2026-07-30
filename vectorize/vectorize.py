"""
Entrypoint for the Vectorization Pipeline.
"""
import time
import sys
import argparse
from pathlib import Path

# When this file is executed directly (``python vectorize/vectorize.py``),
# Python puts only ``vectorize/`` on sys.path. Add the project root so that
# top-level packages such as ``utils`` remain importable.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger
from utils.config import get_settings

from vectorize.repository.warehouse_repository import WarehouseRepository
from vectorize.repository.vector_repository import VectorRepository
from vectorize.embedder.bedrock import BedrockEmbedder
from vectorize.service import VectorizeService

logger = get_logger(__name__)
settings = get_settings()

def run_vectorization(limit: int | None = None, article_id: int | None = None, article_ids: list[int] = None):
    """
    Run the vectorization process.
    Fetches article chunks from the warehouse, generates embeddings, and stores them in the vector repository.
    """
    try:
        warehouse_repo = WarehouseRepository()
        vector_repo = VectorRepository()
        embedder = BedrockEmbedder()
        service = VectorizeService(
            warehouse_repository=warehouse_repo,
            embedder=embedder,
            vector_store=vector_repo
            )

        vector_repo.init_schema()

        logger.info("[EMBEDDING] Vectorization Worker started...")

        if article_id is not None:
            logger.info(f"[EMBEDDING] Running manual job for single article: {article_id}")
            service.process_single_article(article_id)
            
        elif article_ids is not None and len(article_ids) > 0:
            logger.info(f"[EMBEDDING] Running manual job for {len(article_ids)} articles.")
            service.process_batch_by_article_ids(article_ids)
            
        else:
            logger.info(f"[EMBEDDING] Running scheduled batch job (size={limit})")
            service.process_batch(batch_size=limit)

        logger.info("[EMBEDDING] Vectorization Job completed successfully.")

    except Exception as e:
        logger.exception(f"[ERROR] Vectorization pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Article Vectorization Pipeline.")
    parser.add_argument(
        "--batch", 
        type=int, 
        default=500, 
        help="Number of chunks to process in batch mode (default: 500)."
    )
    parser.add_argument(
        "--article-id", 
        type=int, 
        help="Process a single article by its ID."
    )
    parser.add_argument(
        "--article-ids", 
        type=int, 
        nargs="+", 
        help="Process multiple articles by their IDs (separated by space)."
    )

    args = parser.parse_args()

    try:
        run_vectorization(
            limit=args.batch,
            article_id=args.article_id,
            article_ids=args.article_ids
        )
    except KeyboardInterrupt:
        logger.info("\n[EMBEDDING] Job stopped by user (KeyboardInterrupt).")
        sys.exit(0)
