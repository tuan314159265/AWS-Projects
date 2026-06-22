import os
from dotenv import load_dotenv
import json
import hashlib
import psycopg2
from confluent_kafka import Consumer

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

def get_postgres_conn():
    return psycopg2.connect(**PG_CONFIG)

conf = {
    'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
    'group.id': 'newsrag_group',
    'auto.offset.reset': 'earliest'
}

def start_processing():
    print("[Consumer] Initializing Kafka and DB connections...")

    consumer = Consumer(conf)
    consumer.subscribe([os.getenv('KAFKA_TOPIC_NEWS', 'news_raw')])

    pg_conn = get_postgres_conn()

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                print(f"[Kafka Error]: {msg.error()}")
                continue

            try:
                raw_data = msg.value().decode('utf-8')
                data = json.loads(raw_data)

                url = data.get('url', '')
                title = data.get('title', 'Unknown Title')
                author = data.get('author', 'Unknown')
                publish_date = data.get('publish_date', None)

                if not url:
                    continue

                url_hash = hashlib.sha256(url.encode()).hexdigest()

                with pg_conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO article_metadata (url_hash, url, title, content, author, publish_date)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url_hash) DO NOTHING;
                    """, (url_hash, url, title, raw_data, author, publish_date))

                pg_conn.commit()
                print(f"[OK] {title[:50]}...")

            except psycopg2.InterfaceError:
                print("[DB] Connection lost, reconnecting...")
                pg_conn = get_postgres_conn()
            except Exception as e:
                pg_conn.rollback()
                print(f"[ERROR] Skipping article: {e}")

    except KeyboardInterrupt:
        print("\n[Consumer] Stopping...")
    finally:
        consumer.close()
        if pg_conn:
            pg_conn.close()

if __name__ == "__main__":
    start_processing()
