#!/usr/bin/env python3
"""Bulk migrate article_metadata → star-schema on RDS."""
import psycopg2, hashlib, sys, json
from datetime import datetime

conn = psycopg2.connect(
    host="newsrag-instance-1.cn8uwuau2s7x.ap-southeast-2.rds.amazonaws.com",
    database="postgres", user="newsrag_admin", password="newsrag_admin", port=5432
)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS fact_article_authors, fact_articles, dim_content, dim_author, dim_time, dim_source CASCADE")
cur.execute("CREATE TABLE dim_source (source_id SERIAL PRIMARY KEY, domain TEXT UNIQUE)")
cur.execute("CREATE TABLE dim_time (time_id SERIAL PRIMARY KEY, date DATE UNIQUE, day INT, month INT, year INT, quarter INT)")
cur.execute("CREATE TABLE dim_author (author_id SERIAL PRIMARY KEY, author_name TEXT UNIQUE)")
cur.execute("CREATE TABLE dim_content (content_id SERIAL PRIMARY KEY, content_hash TEXT UNIQUE, content TEXT)")
cur.execute("CREATE TABLE fact_articles (article_id SERIAL PRIMARY KEY, title TEXT, url_hash TEXT UNIQUE, source_id INT, time_id INT, content_id INT)")
cur.execute("CREATE TABLE fact_article_authors (article_id INT, author_id INT, PRIMARY KEY (article_id, author_id))")

f = open("data/articles.json").read().strip().rstrip(",")
if not f.endswith("]"): f += "]"
data = json.loads(f)
print(f"Loaded {len(data)} articles", flush=True)

# Bulk dim_source
domains = list(set(d.get("source", "") for d in data))
for d in domains:
    cur.execute("INSERT INTO dim_source (domain) VALUES (%s) ON CONFLICT (domain) DO NOTHING", (d,))
cur.execute("SELECT domain, source_id FROM dim_source")
source_map = dict(cur.fetchall())
print(f"  dim_source: {len(source_map)}", flush=True)

# Bulk dim_time
dates_seen = set()
for d in data:
    pd = d.get("publish_date", "")
    if pd and pd != "Unknown":
        try:
            dt = datetime.strptime(pd, "%Y-%m-%d %H:%M:%S")
            dates_seen.add((dt.date(), dt.day, dt.month, dt.year, (dt.month-1)//3+1))
        except: pass
for tup in dates_seen:
    cur.execute("INSERT INTO dim_time (date, day, month, year, quarter) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (date) DO NOTHING", tup)
cur.execute("SELECT date, time_id FROM dim_time")
time_map = {str(r[0]): r[1] for r in cur.fetchall()}
print(f"  dim_time: {len(time_map)}", flush=True)

# Bulk dim_author
authors_seen = set()
for d in data:
    a = d.get("author", "")
    if a and a != "Unknown":
        authors_seen.add(a)
for a in authors_seen:
    cur.execute("INSERT INTO dim_author (author_name) VALUES (%s) ON CONFLICT (author_name) DO NOTHING", (a,))
cur.execute("SELECT author_name, author_id FROM dim_author")
author_map = dict(cur.fetchall())
print(f"  dim_author: {len(author_map)}", flush=True)

# Bulk dim_content + fact_articles
count = 0
for d in data:
    url = d.get("url", "")
    url_hash = hashlib.md5(url.encode()).hexdigest()
    title = d.get("title")
    content = d.get("content", "")
    ch = hashlib.md5((content or "").encode()).hexdigest()

    cur.execute("INSERT INTO dim_content (content_hash, content) VALUES (%s,%s) ON CONFLICT (content_hash) DO NOTHING", (ch, content))
    cur.execute("SELECT content_id FROM dim_content WHERE content_hash = %s", (ch,))
    content_id = cur.fetchone()[0]

    sid = source_map.get(d.get("source", ""))
    tid = None
    pd = d.get("publish_date", "")
    if pd and pd != "Unknown":
        try:
            dt = datetime.strptime(pd, "%Y-%m-%d %H:%M:%S")
            tid = time_map.get(str(dt.date()))
        except: pass

    cur.execute("INSERT INTO fact_articles (title, url_hash, source_id, time_id, content_id) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (url_hash) DO NOTHING RETURNING article_id",
                (title, url_hash, sid, tid, content_id))
    row = cur.fetchone()
    if row:
        article_id = row[0]
        a = d.get("author", "")
        if a and a != "Unknown" and a in author_map:
            cur.execute("INSERT INTO fact_article_authors VALUES (%s,%s) ON CONFLICT DO NOTHING", (article_id, author_map[a]))

    count += 1
    if count % 200 == 0:
        conn.commit()
        print(f"  ... {count}/{len(data)}", flush=True)

conn.commit()

for tbl in ["dim_source", "dim_time", "dim_author", "dim_content", "fact_articles", "fact_article_authors"]:
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    print(f"  {tbl}: {cur.fetchone()[0]}", flush=True)
conn.close()
print("Done", flush=True)