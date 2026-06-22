import os
import json
import multiprocessing
import time
import argparse
import schedule

import consumer.consumer as consumer_module
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler.spiders.spider import NewsRAGSpider

from etl.etl_warehouse import run_etl_warehouse
from vectorize.vectorize import run_vectorization

def run_spider(site_url):
    """Run a single spider in a separate process."""
    settings = get_project_settings()
    settings.set('CLOSESPIDER_TIMEOUT', 600)
    process = CrawlerProcess(settings)
    process.crawl(NewsRAGSpider, start_urls=[site_url])
    process.start()

def run_consumer():
    """Run Kafka consumer in a separate process."""
    print("[Consumer] Initializing connection...")
    time.sleep(2)
    consumer_module.start_processing()

def do_crawl_stage():
    """Crawl news sites and store raw data via Kafka -> PostgreSQL."""
    config_path = 'config/config_site.json'
    if not os.path.exists(config_path):
        print(f"[ERROR] Config not found: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        sites = json.load(f)
    urls = [s['url'] if isinstance(s, dict) else s for s in sites]

    all_processes = []
    p_cons = None

    try:
        # 1. Start consumer first
        p_cons = multiprocessing.Process(target=run_consumer, name="Consumer-Process")
        p_cons.start()
        all_processes.append(p_cons)
        time.sleep(5)

        # 2. Run spiders in parallel
        print(f"Starting {len(urls)} Spiders (timeout: 10 min)...")
        spider_processes = []
        for url in urls:
            p_spider = multiprocessing.Process(target=run_spider, args=(url,), name=f"Spider-{url}")
            p_spider.start()
            spider_processes.append(p_spider)
            all_processes.append(p_spider)

        # 3. Wait for spiders to finish
        for p in spider_processes:
            p.join()

        time.sleep(20)

        # 4. Stop consumer
        if p_cons and p_cons.is_alive():
            p_cons.terminate()
            p_cons.join()

    except KeyboardInterrupt:
        for p in all_processes:
            if p.is_alive():
                p.terminate()
                p.join()

def do_balance_etl_and_vectorize():
    """Alternate ETL and Vectorize to balance memory usage."""
    while True:
        etl_count = run_etl_warehouse(limit=50)
        vec_count = run_vectorization(limit=256)

        if etl_count == 0 and vec_count == 0:
            print("[DONE] Pipeline complete. No pending data.")
            break

        time.sleep(2)

def run_full_pipeline():
    """Run the complete pipeline: crawl -> ETL -> vectorize."""
    do_crawl_stage()
    do_balance_etl_and_vectorize()

if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser(description="News RAG Pipeline")
    parser.add_argument('--mode', type=str, choices=['crawl', 'etl', 'vectorize', 'full', 'auto'],
                        default='full',
                        help='Mode: crawl | etl | vectorize | full | auto (3 runs/day)')
    args = parser.parse_args()

    if args.mode == 'crawl':
        do_crawl_stage()
    elif args.mode == 'etl':
        run_etl_warehouse(limit=None)
    elif args.mode == 'vectorize':
        run_vectorization(limit=None)
    elif args.mode == 'full':
        run_full_pipeline()
    elif args.mode == 'auto':
        print("[AUTO] Scheduling 3 runs/day (08:00, 14:00, 20:00)")
        schedule.every().day.at("08:00").do(run_full_pipeline)
        schedule.every().day.at("14:00").do(run_full_pipeline)
        schedule.every().day.at("20:00").do(run_full_pipeline)
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            print("[AUTO] Stopped.")
