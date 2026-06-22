import os
import psycopg2
import json
import re
from dotenv import load_dotenv
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path)

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432))
}

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    junk_patterns = [
        r"Chia sẻ bài viết qua email", r"Ảnh:.*?\.", r"Video:.*?\.",
        r"Độc giả.*?\.", r"Bản quyền thuộc về.*", r"Hãy gửi câu hỏi về.*"
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()

def init_warehouse_schema(cur, conn):
    try:
        with open('database/warehouse.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
            cur.execute(sql_script)
            conn.commit()
    except FileNotFoundError:
        print("[LỖI] Không tìm thấy file warehouse.sql.")
    except Exception as e:
        conn.rollback()
        print(f"[LỖI] Không thể tải warehouse.sql: {e}")

def run_etl_warehouse(limit=None):
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        init_warehouse_schema(cur, conn)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=150,
            separators=["\n\n", "\n", ".", " ", ""]
        )

        cur.execute("SELECT url_hash FROM fact_articles")
        existing_hashes = {row[0] for row in cur.fetchall()}

        cur.execute("SELECT url_hash, title, content, url FROM article_metadata")
        rows = cur.fetchall()

        if not rows:
            print("[!] Không có dữ liệu trong article_metadata.")
            return 0

        seen_titles = set()
        raw_rows = []
        for row in rows:
            url_hash, current_title = row[0], row[1]
            if url_hash not in existing_hashes and current_title not in seen_titles:
                seen_titles.add(current_title)
                raw_rows.append(row)

        total_new = len(raw_rows)
        if total_new == 0:
            print("[OK] ETL đã Up-to-date!")
            return 0

        print(f"[*] Bắt đầu xử lý {total_new} bài viết mới...")

        processed_count = 0
        skipped_count = 0
        error_count = 0

        for idx, (url_hash, title, content_raw, url) in enumerate(raw_rows, 1):
            progress = f"[{idx}/{total_new}]"

            try:
                data = content_raw if isinstance(content_raw, dict) else json.loads(content_raw)

                raw_authors = data.get('author', 'Unknown')
                p_date_str = data.get('publish_date', 'Unknown')
                if not raw_authors or raw_authors == "Unknown" or not p_date_str or p_date_str == "Unknown":
                    cur.execute("DELETE FROM article_metadata WHERE url_hash = %s", (url_hash,))
                    conn.commit()
                    skipped_count += 1
                    continue

                cleaned_text = clean_text(data.get('content', ''))

                if isinstance(raw_authors, str):
                    clean_authors = re.sub(r'\(.*?\)', '', raw_authors)
                    clean_authors = re.split(r'(?i)\s+và\s+', clean_authors)[0]
                    raw_list = re.split(r',|\s*-\s*', clean_authors)
                    author_list = [a.strip() for a in raw_list if a.strip()]
                    if not author_list:
                        author_list = ["Unknown"]
                else:
                    author_list = raw_authors

                domain = url.split('/')[2] if '//' in url else url
                cur.execute("""
                    INSERT INTO dim_source (domain) VALUES (%s)
                    ON CONFLICT (domain) DO UPDATE SET domain = EXCLUDED.domain
                    RETURNING source_id
                """, (domain,))
                source_id = cur.fetchone()[0]

                if p_date_str == "Unknown" or not p_date_str:
                    dt = datetime.now()
                else:
                    try:
                        dt = datetime.strptime(p_date_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        dt = datetime.now()
                try:
                    cur.execute("""
                        INSERT INTO dim_time (date, day, month, year)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (date) DO UPDATE SET date = EXCLUDED.date
                        RETURNING time_id
                    """, (dt.date(), dt.day, dt.month, dt.year))
                    time_id = cur.fetchone()[0]
                except:
                    time_id = 0

                cur.execute("""
                    INSERT INTO dim_content (url_hash, content)
                    VALUES (%s, %s) ON CONFLICT (url_hash)
                    DO UPDATE SET content = EXCLUDED.content RETURNING content_id
                """, (url_hash, cleaned_text))
                content_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO fact_articles (url_hash, title, source_id, time_id, content_id, content_length)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url_hash) DO UPDATE SET title = EXCLUDED.title
                    RETURNING article_id
                """, (url_hash, title, source_id, time_id, content_id, len(cleaned_text)))
                article_id = cur.fetchone()[0]

                cur.execute("DELETE FROM fact_article_authors WHERE article_id = %s", (article_id,))
                delete_article = False
                for name in author_list:
                    curr_name = name.strip() if name else "Unknown"
                    invalid_author = (
                        len(curr_name) > 40
                        or "http" in curr_name.lower()
                        or "/" in curr_name
                        or "|" in curr_name
                        or "@" in curr_name
                    )
                    if invalid_author:
                        cur.execute("DELETE FROM fact_article_authors WHERE article_id = %s", (article_id,))
                        cur.execute("DELETE FROM fact_chunks WHERE article_id = %s", (article_id,))
                        cur.execute("DELETE FROM fact_articles WHERE article_id = %s", (article_id,))
                        delete_article = True
                        break
                    cur.execute("""
                        INSERT INTO dim_author (author_name) VALUES (%s)
                        ON CONFLICT (author_name) DO UPDATE SET author_name = EXCLUDED.author_name
                        RETURNING author_id
                    """, (curr_name,))
                    curr_auth_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO fact_article_authors (article_id, author_id)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """, (article_id, curr_auth_id))

                if delete_article:
                    cur.execute("DELETE FROM article_metadata WHERE url_hash = %s", (url_hash,))
                    conn.commit()
                    skipped_count += 1
                    continue

                cur.execute("DELETE FROM fact_chunks WHERE article_id = %s", (article_id,))
                chunks = text_splitter.split_text(cleaned_text)
                for i, chunk_text in enumerate(chunks):
                    clean_chunk = chunk_text.lstrip('. ,!?\n\t')
                    if clean_chunk:
                        cur.execute("INSERT INTO fact_chunks (article_id, chunk_index, content) VALUES (%s, %s, %s)",
                                    (article_id, i, clean_chunk))

                processed_count += 1
                print(f"{progress} [OK] {title[:40]}...")

                if processed_count % 50 == 0:
                    conn.commit()

            except Exception as e:
                conn.rollback()
                error_count += 1
                print(f"{progress} [LỖI] {title[:30]}: {e}")

        conn.commit()
        print(f"\n[HOÀN TẤT] Đã xử lý: {processed_count} | Bỏ qua: {skipped_count} | Lỗi: {error_count}")
        return processed_count

    except Exception as e:
        print(f"[!] Lỗi kết nối hoặc xử lý: {e}")
        return 0
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == "__main__":
    run_etl_warehouse()
