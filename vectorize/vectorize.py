import os
import psycopg2
import uuid
import time
from datetime import datetime
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path)

PG_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432))
}

QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_SIZE = int(os.getenv("EMBEDDING_SIZE", 384))


def generate_uuid(article_id, chunk_index):
    unique_string = f"article_{article_id}_chunk_{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))


def run_vectorization(limit=None):
    print(f"[*] Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    qdrant = QdrantClient(
        url=f"https://{QDRANT_HOST}",
        api_key=QDRANT_API_KEY
    )

    if not qdrant.collection_exists(COLLECTION_NAME):
        print(f"[*] Creating collection '{COLLECTION_NAME}'...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_SIZE, distance=Distance.COSINE)
        )
    else:
        print(f"[*] Collection '{COLLECTION_NAME}' already exists.")

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()

        print("[*] Fetching chunks from PostgreSQL...")
        query = """
            SELECT
                c.article_id, c.chunk_index, c.content, a.title, m.url,
                COALESCE(t.date::text, 'Unknown') as publish_date,
                COALESCE(string_agg(DISTINCT au.author_name, ', '), 'Unknown') as authors
            FROM fact_chunks c
            JOIN fact_articles a ON c.article_id = a.article_id
            JOIN article_metadata m ON a.url_hash = m.url_hash
            LEFT JOIN dim_time t ON a.time_id = t.time_id
            LEFT JOIN fact_article_authors faa ON a.article_id = faa.article_id
            LEFT JOIN dim_author au ON faa.author_id = au.author_id
            GROUP BY c.article_id, c.chunk_index, c.content, a.title, m.url, t.date
        """
        cur.execute(query)
        all_chunks = cur.fetchall()

        if not all_chunks:
            print("[!] No chunks in Warehouse.")
            return 0

        print("[*] Checking existing vectors in Qdrant...")
        chunks_to_process = []
        all_point_ids = [generate_uuid(row[0], row[1]) for row in all_chunks]
        existing_ids = set()

        for i in range(0, len(all_point_ids), 1000):
            batch_ids = all_point_ids[i:i+1000]
            try:
                results = qdrant.retrieve(collection_name=COLLECTION_NAME, ids=batch_ids)
                existing_ids.update([res.id for res in results])
            except Exception:
                pass

        for row in all_chunks:
            point_id = generate_uuid(row[0], row[1])
            if point_id not in existing_ids:
                chunks_to_process.append(row)
                if limit and len(chunks_to_process) >= limit:
                    break

        total_new = len(chunks_to_process)
        if total_new == 0:
            print("[OK] Vector store is up-to-date!")
            return 0

        print(f"[*] Vectorizing {total_new} new chunks...")

        ENCODE_BATCH_SIZE = 64
        points = []

        for i in range(0, total_new, ENCODE_BATCH_SIZE):
            batch_rows = chunks_to_process[i:i+ENCODE_BATCH_SIZE]
            batch_contents = [row[2] for row in batch_rows]

            embeddings = model.encode(batch_contents, normalize_embeddings=True)

            for j, row in enumerate(batch_rows):
                article_id, chunk_index, content, title, url, publish_date, authors = row
                point_id = generate_uuid(article_id, chunk_index)

                timestamp = 0
                if publish_date and publish_date != 'Unknown':
                    try:
                        date_str = str(publish_date)[:10]
                        dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        timestamp = int(time.mktime(dt_obj.timetuple()))
                    except Exception:
                        pass

                point = PointStruct(
                    id=point_id,
                    vector=embeddings[j].tolist(),
                    payload={
                        "article_id": article_id,
                        "chunk_index": chunk_index,
                        "title": title,
                        "url": url,
                        "content": content,
                        "authors": authors,
                        "publish_timestamp": timestamp
                    }
                )
                points.append(point)

            if len(points) >= 256:
                qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
                print(f"  [+] Upserted {min(i + ENCODE_BATCH_SIZE, total_new)}/{total_new} chunks...")
                points = []

        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  [+] Upserted {total_new}/{total_new} chunks...")

        print(f"\n[OK] Successfully vectorized {total_new} chunks into Qdrant!")
        return total_new

    except Exception as e:
        print(f"[ERROR] Vectorization failed: {e}")
        return 0
    finally:
        if cur: cur.close()
        if conn: conn.close()


if __name__ == "__main__":
    run_vectorization(limit=None)
