"""
Vector Store Repository.

This module handles storing and searching embeddings in PostgreSQL using pgvector.
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
from ..schemas import Chunk, VectorRecord

settings = get_settings()
logger = get_logger(__name__)

class VectorRepository:
    """
    PostgreSQL vector repository using pgvector.
    Handles inserting vectors and performing semantic search.
    """

    def __init__(self) -> None:
        "Initialize the repository with the database connection string."
        self._config = settings.database
        self._embedding_dim = settings.vector_store.embedding_dimension

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

    def init_schema(self) -> None:
        """
        Create the vector table and HNSW index if they don't exist.
        """
        logger.info("[VECTOR_STORE] Initializing database schema for vectors...")

        sql_create_extension = "CREATE EXTENSION IF NOT EXISTS vector;"

        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS fact_vectors (
                article_id BIGINT NOT NULL,
                chunk_index INT NOT NULL,
                embedding vector({self._embedding_dim}),
                PRIMARY KEY (article_id, chunk_index)
            );
        """

        sql_create_index = """
            CREATE INDEX IF NOT EXISTS idx_fact_vectors_hnsw 
            ON fact_vectors USING hnsw (embedding vector_cosine_ops);
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql_create_extension)
                    cursor.execute(create_table_query)
                    cursor.execute(sql_create_index)
                    conn.commit()
            logger.info("[VECTOR_STORE] Initialized database schema for vectors.")
        except psycopg2.Error:
            logger.exception("[VECTOR_STORE] Error occurred while initializing database schema.")
            raise

    def upsert_vectors(self, vector_records: list[VectorRecord]) -> None:
        """
        Upsert a batch of vector records into the database.
        """
        if not vector_records:
            logger.warning("[VECTOR_STORE] No vector records provided for upsert.")
            return

        logger.info("[VECTOR_STORE] Upserting %d vector records into the database...", len(vector_records))

        upsert_query = f"""
            INSERT INTO fact_vectors (article_id, chunk_index, embedding)
            VALUES %s
            ON CONFLICT (article_id, chunk_index) 
            DO UPDATE SET embedding = EXCLUDED.embedding;
        """

        data_to_insert = [(record.article_id, record.chunk_index, record.embedding) 
                  for record in vector_records]

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    execute_values(cursor, upsert_query, data_to_insert)
                    conn.commit()
                logger.info("[VECTOR_STORE] Successfully upserted %d vector records.", len(vector_records))
        except Exception as e:
            logger.exception(f"[VECTOR_STORE] Error occurred while upserting vector records as {e}.")
            raise

    def search_vectors(self, query_embedding: list[float], top_k: int = 20) -> list[tuple[Chunk, float]]:
        """
        Perform a semantic search for the top_k most similar vectors to the query_embedding.
        """
        logger.info("[VECTOR_STORE] Performing semantic search for top %d vectors...", top_k)

        search_query = """
            WITH top_vectors AS (
                SELECT article_id, chunk_index, embedding, (embedding <=> %s::vector) AS distance
                FROM fact_vectors
                ORDER BY distance ASC
                LIMIT %s
            )
            SELECT
                c.article_id, c.chunk_index, c.content, a.title, m.url,
                COALESCE(string_agg(DISTINCT au.author_name, ', '), 'Unknown') AS authors,
                COALESCE(t.date::text, 'Unknown') AS publish_date,
                tv.distance
            FROM top_vectors tv
            JOIN fact_chunks c ON tv.article_id = c.article_id AND tv.chunk_index = c.chunk_index
            JOIN fact_articles a ON c.article_id = a.article_id
            JOIN article_metadata m ON a.url_hash = m.url_hash
            LEFT JOIN dim_time t ON a.time_id = t.time_id
            LEFT JOIN fact_article_authors faa ON faa.article_id = a.article_id
            LEFT JOIN dim_author au ON au.author_id = faa.author_id
            GROUP BY c.article_id, c.chunk_index, c.content, a.title, m.url, t.date, tv.distance
            ORDER BY tv.distance ASC;
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(search_query, (query_embedding, top_k))
                    rows = cursor.fetchall()
            
            results = []
            for row in rows:
                chunk = self._to_chunk(row)
                distance = float(row["distance"])
                results.append((chunk, distance))

            return results
        except Exception as e:
            logger.exception(f"[VECTOR_STORE] Semantic search failed due to {e}")
            raise
    
    @staticmethod
    def _to_chunk(row: dict) -> Chunk:
        """
        Convert a database row to a Chunk object.
        """
        timestamp = 0
        date_str = row.get("publish_date", "Unknown")
        if date_str and date_str != "Unknown":
            try:
                timestamp = int(datetime.strptime(date_str[:10], "%Y-%m-%d").timestamp())
            except ValueError:
                timestamp = 0

        return Chunk(
            article_id=row["article_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            title=row.get("title"),
            url=row.get("url"),
            authors=row.get("authors"),
            publish_timestamp=timestamp
        )