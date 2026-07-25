import os
import json
import multiprocessing
import time
import argparse
import schedule


from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler.spiders.spider import NewsRAGSpider

from etl.etl_warehouse import run_etl_warehouse
from vectorize.vectorize import run_vectorization


def run_spider(site_url):
    """Chạy một spider trong process riêng."""
    settings = get_project_settings()
    settings.set('CLOSESPIDER_TIMEOUT', 600)
    process = CrawlerProcess(settings)
    process.crawl(NewsRAGSpider, start_urls=[site_url])
    process.start()



def do_crawl_stage():
    """Cào tin tức từ các báo và lưu qua Kafka -> PostgreSQL."""
    config_path = 'config/config_site.json'
    if not os.path.exists(config_path):
        print(f"[LỖI] Không tìm thấy config: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        sites = json.load(f)
    urls = [s['url'] if isinstance(s, dict) else s for s in sites]

    all_processes = []
    p_cons = None

    try:
        # 2. Chạy Spiders song song
        print(f"Bắt đầu {len(urls)} Spiders (thời gian chạy: 10 phút)...")
        spider_processes = []
        for url in urls:
            p_spider = multiprocessing.Process(target=run_spider, args=(url,), name=f"Spider-{url}")
            p_spider.start()
            spider_processes.append(p_spider)
            all_processes.append(p_spider)

        # 3. Đợi Spiders hoàn thành
        for p in spider_processes:
            p.join()

        time.sleep(20)



    except KeyboardInterrupt:
        for p in all_processes:
            if p.is_alive():
                p.terminate()
                p.join()


def do_balance_etl_and_vectorize():
    """Chạy luân phiên ETL và Vectorize để cân bằng bộ nhớ."""
    while True:
        etl_count = run_etl_warehouse(limit=4000)
        vec_count = run_vectorization(batch_size=4000)

        if etl_count == 0 and vec_count == 0:
            print("[HOÀN TẤT] Pipeline đã xử lý xong toàn bộ dữ liệu.")
            break

        time.sleep(2)


def run_full_pipeline():
    """Chạy pipeline hoàn chỉnh: crawl -> ETL -> vectorize."""
    do_crawl_stage()
    do_balance_etl_and_vectorize()


if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser(description="Pipeline Tin tức RAG")
    parser.add_argument('--mode', type=str, choices=['crawl', 'etl', 'vectorize', 'full', 'auto'],
                        default='full',
                        help='Chế độ: crawl | etl | vectorize | full | auto (3 ca/ngày)')
    args = parser.parse_args()

    if args.mode == 'crawl':
        do_crawl_stage()
    elif args.mode == 'etl':
        run_etl_warehouse(limit=None)
    elif args.mode == 'vectorize':
        run_vectorization(batch_size=None)
    elif args.mode == 'full':
        run_full_pipeline()
    elif args.mode == 'auto':
        print("[AUTO] Đang đặt lịch chạy tự động (08:00, 14:00, 20:00)...")
        schedule.every().day.at("08:00").do(run_full_pipeline)
        schedule.every().day.at("14:00").do(run_full_pipeline)
        schedule.every().day.at("20:00").do(run_full_pipeline)
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            print("[AUTO] Đã dừng.")
