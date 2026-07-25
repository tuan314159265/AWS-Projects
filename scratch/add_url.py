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
    cur.execute("ALTER TABLE fact_articles ADD COLUMN url TEXT")
    conn.commit()
    print("Added url to fact_articles")
except Exception as e:
    print(f"Error: {e}")
cur.close()
conn.close()
