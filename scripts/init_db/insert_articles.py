#!/usr/bin/env python3
import psycopg2, json, hashlib, sys

conn = psycopg2.connect(
    host="newsrag-instance-1.cn8uwuau2s7x.ap-southeast-2.rds.amazonaws.com",
    database="postgres", user="newsrag_admin", password="newsrag_admin", port=5432
)
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS article_metadata")
cur.execute("""
    CREATE TABLE article_metadata (
        url_hash TEXT PRIMARY KEY, title TEXT, url TEXT,
        content TEXT, author TEXT, source TEXT,
        publish_date TEXT, crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

f = open(sys.argv[1]).read().strip().rstrip(",")
if not f.endswith("]"): f += "]"
data = json.loads(f)

for d in data:
    url = d.get("url", "")
    uh = hashlib.md5(url.encode()).hexdigest()
    cur.execute("INSERT INTO article_metadata VALUES (%s,%s,%s,%s,%s,%s,%s,DEFAULT) ON CONFLICT DO NOTHING",
        (uh, d.get("title"), url, d.get("content"), d.get("author",""), d.get("source",""), d.get("publish_date","")))

conn.commit()
cur.execute("SELECT COUNT(*) FROM article_metadata")
print(f"OK: {cur.fetchone()[0]} articles")
conn.close()
