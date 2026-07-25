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
    cur.execute("SELECT COUNT(*) FROM fact_vectors")
    print(f"Vectors in DB: {cur.fetchone()[0]}")
except Exception as e:
    print(f"Error: {e}")
cur.close()
conn.close()
