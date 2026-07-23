"""
Base embedding module.

This module defines the abstract base class (Strategy Pattern) 
for all embedders within the RAG system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from utils.logger import get_logger
from ..schemas import Chunk


class BaseEmbedder(ABC):
    """
    Abstract base class for text embedders.
    """

    @abstractmethod
    def embed(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Generate and assign vector embeddings for a list of chunks.

        Parameters
        ----------
        chunks : list[Chunk]
            The list of Chunk objects that require vectorization.

        Returns
        -------
        list[Chunk]
            The same list of Chunk objects, mutated to include 
            their respective vector embeddings.
        """
        pass

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """
        Generate a vector embedding for a single query string.

        Parameters
        ----------
        query : str
            The input query string to be vectorized.

        Returns
        -------
        list[float]
            The vector embedding corresponding to the input query.
        """
        pass