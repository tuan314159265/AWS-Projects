"""
Warehouse repository.

This module provides data access methods for the PostgreSQL data warehouse,
specifically for fetching un-embedded text chunks.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from datetime import datetime

import psycopg2
from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor, execute_values
from pgvector.psycopg2 import register_vector

from utils.config import get_settings
from utils.logger import get_logger
from ..schemas import Chunk



settings = get_settings()
logger = get_logger(__name__)


class WarehouseRepository:
    """
    PostgreSQL vector repository using pgvector.
    Handles inserting vectors and performing semantic search.
    """

    def __init__(self) -> None:
        "Initialize the repository with the database connection string."
        self._config = settings.database


    @contextmanager
    def _get_connection(self) -> Iterator[connection]:
        """Context manager to provide a database connection safely."""
        conn = None
        try:
            conn = psycopg2.connect(self._config.url)
            register_vector(conn)
            yield conn
        except psycopg2.Error:
            logger.exception("[VECTOR_STORE] Database connection error.")
            raise
        finally:
            if conn is not None:
                conn.close()

    def fetch_chunks(
        self,
        limit: int | None = None,
    ) -> list[Chunk]:
        """
        Fetch article chunks from the warehouse.
        """

        query = self._build_query(has_limit=limit is not None)
        logger.info("[EMBEDDING] Fetching chunks from warehouse...")

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    if limit:
                        cursor.execute(query, (limit,))
                    else:
                        cursor.execute(query)

                    rows = cursor.fetchall()
        except psycopg2.Error:
            logger.exception("[EMBEDDING] Database error occurred while fetching chunks.")
            raise

        chunks = [self._to_chunk(row) for row in rows]
        logger.info("[EMBEDDING] Fetched %d chunks from warehouse.", len(chunks))

        return chunks

    def fetch_chunks_by_article(self, article_id: int) -> list[Chunk]:
        """
        Fetch all chunks for a specific article.
        """
        query = self._build_query(filter_article_id=True)
        logger.info("[EMBEDDING] Fetching chunks for article: %s", article_id)

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (article_id,))
                    rows = cursor.fetchall()
            
            chunks = [self._to_chunk(row) for row in rows]
            return chunks
        except psycopg2.Error:
            logger.exception("[EMBEDDING] Error fetching chunks for article: %s", article_id)
            raise
    
    @staticmethod
    def _build_query(filter_article_id: bool = False, has_limit: bool = False) -> str:
        """Build the base SQL query."""
        sql = """
            SELECT
                c.article_id, c.chunk_index, c.content, a.title, m.url,
                COALESCE(string_agg(DISTINCT au.author_name, ', '), 'Unknown') AS authors,
                COALESCE(t.date::text, 'Unknown') AS publish_date
            FROM fact_chunks c
            JOIN fact_articles a ON c.article_id = a.article_id
            JOIN article_metadata m ON a.url_hash = m.url_hash
            LEFT JOIN dim_time t ON a.time_id = t.time_id
            LEFT JOIN fact_article_authors faa ON faa.article_id = a.article_id
            LEFT JOIN dim_author au ON au.author_id = faa.author_id

            LEFT JOIN fact_vectors v ON c.article_id = v.article_id AND c.chunk_index = v.chunk_index
            WHERE v.embedding IS NULL
        """
        
        if filter_article_id:
            sql += "\nWHERE c.article_id = %s\n"
            
        sql += """
            GROUP BY c.article_id, c.chunk_index, c.content, a.title, m.url, t.date
            ORDER BY c.chunk_index
        """
        
        if has_limit:
            sql += "\nLIMIT %s\n"
        
        return sql

    @staticmethod
    def _to_chunk(row: dict) -> Chunk:
        """
        Convert database row into Chunk.
        """

        timestamp = 0
        publish_date = row.get("publish_date", "Unknown")

        if publish_date != "Unknown":
            try:

                dt = datetime.strptime(
                    publish_date[:10],
                    "%Y-%m-%d",
                )

                timestamp = int(dt.timestamp())

            except Exception:
                logger.exception("[EMBEDDING] Error occurred while parsing publish date: %s", 
                                 publish_date,
                                 row.get("article_id"))
                timestamp = 0

        return Chunk(
            article_id=row["article_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            title=row["title"],
            url=row["url"],
            authors=row["authors"],
            publish_timestamp=timestamp,
        )
    
    