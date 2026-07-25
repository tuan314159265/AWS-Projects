import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST'),
    port=5432
)
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE dim_content RENAME COLUMN content_hash TO url_hash")
    conn.commit()
    print("Renamed content_hash to url_hash in dim_content")
except Exception as e:
    conn.rollback()
    print(f"Error renaming: {e}")

try:
    cur.execute("ALTER TABLE fact_articles ADD COLUMN content_length INT")
    conn.commit()
    print("Added content_length to fact_articles")
except Exception as e:
    conn.rollback()
    print(f"Error adding: {e}")

cur.close()
conn.close()
