"""
Data schemas for the vectorization pipeline.

This module defines the shared data models exchanged between
the repository, embedding service and vector store.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid5, NAMESPACE_DNS

from utils.logger import get_logger

logger = get_logger(__name__)



# =============================================================================
# Warehouse Chunk
# =============================================================================


@dataclass(slots=True)
class Chunk:
    """
    Represents one chunk retrieved from the warehouse.

    Parameters
    ----------
    id:
        Unique chunk identifier.

    embedding:
        Embedding vector.

    article_id:
        Unique article identifier.

    chunk_index:
        Position of the chunk inside the article.

    content:
        Chunk content.

    title:
        Article title.

    url:
        Original article URL.

    authors:
        Comma separated author names.

    publish_timestamp:
        Unix timestamp.
    """
    # Article metadata
    article_id: int

    chunk_index: int

    content: str

    title: str = ""

    url: str = ""

    authors: str = "Unknown"

    publish_timestamp: int = 0

    # Chunk unique identifier, generated from article_id and chunk_index
    id: UUID | None = None

    embedding: list[float] | None = field(default=None)

    def __post_init__(self) -> None:
        try:
            if self.id is None:
                self.id = uuid5(
                    NAMESPACE_DNS,
                    f"article_{self.article_id}_chunk_{self.chunk_index}",
                )
        except Exception as e:
            logger.exception("[CHUNK] Error occurred while generating chunk ID: %s", e)
            raise

    @property
    def is_embedded(self) -> bool:
        """Whether the chunk already has an embedding."""
        return self.embedding is not None


    @property
    def is_indexed(self) -> bool:
        """Whether the chunk already has a UUID."""
        return self.id is not None
    
    @property
    def ready(self) -> bool:
        """
        Whether the chunk is ready to be stored.
        """
        return (
            self.id is not None
            and self.embedding is not None
        )
    
@dataclass
class VectorRecord:
    """
    Represents a record in the vector store.
    """

    article_id: int
    chunk_index: int
    embedding: list[float]




