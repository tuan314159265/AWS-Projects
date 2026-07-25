import os
import json
import re
import platform
import scrapy
from urllib.parse import urlparse
from newspaper import Article
from datetime import datetime


class NewsRAGSpider(scrapy.Spider):
    name = "news_rag_spider"

    is_windows = platform.system() == "Windows"

    custom_settings = {
        "CONCURRENT_REQUESTS": 16 if is_windows else 32,
        "DOWNLOAD_DELAY": 1.0 if is_windows else 0.5,
        "DEPTH_LIMIT": 5,
        "ROBOTSTXT_OBEY": False,
        "LOG_LEVEL": "INFO",
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            if is_windows
            else "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        crawler_dir = os.path.dirname(curr_dir)
        project_root = os.path.dirname(crawler_dir)
        config_path = os.path.abspath(
            os.path.join(project_root, "config", "config_site.json")
        )

        if not os.path.exists(config_path):
            self.logger.error(f"Config not found: {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            sites = json.load(f)
        self.start_urls = [s["url"] if isinstance(s, dict) else s for s in sites]

    def parse(self, response):
        curr_domain = urlparse(response.url).netloc
        all_links = response.css("a::attr(href)").getall()

        for link in all_links:
            if any(link.startswith(x) for x in ["mailto:", "tel:", "javascript:", "#"]):
                continue

            full_url = response.urljoin(link)

            if curr_domain in full_url:
                if any(ext in full_url for ext in [".html", ".htm", ".amp"]):
                    yield response.follow(full_url, callback=self.parse_article)
                elif (
                    len(full_url.replace("https://" + curr_domain, "").split("/")) <= 3
                ):
                    yield response.follow(full_url, callback=self.parse)

    def parse_article(self, response):
        article = Article(response.url)
        article.set_html(response.text)
        try:
            article.parse()
        except:
            return

        if not article.text or len(article.text) < 100:
            return

        author_list = article.authors
        author = ", ".join(author_list).strip() if author_list else ""

        def is_valid_author(name):
            clean_name = name.strip()
            name_lower = clean_name.lower()
            if name_lower in [
                "nguon",
                "theo",
                "anh",
                "bai",
                "tac gia",
                "tong hop",
                "pv",
                "btv",
            ]:
                return False
            if (
                re.match(r"^\d+[\.\-\)]", clean_name)
                or "?" in clean_name
                or "!" in clean_name
            ):
                return False
            if not name or len(name) < 2 or len(name) > 100:
                return False
            if len(re.findall(r"\d", name)) >= 7:
                return False
            if re.search(r"\d{1,2}[/-]\d{1,2}|\d{1,2}:\d{1,2}", name):
                return False
            bad_words = [
                "thu hai",
                "thu ba",
                "thu tu",
                "thu nam",
                "thu sau",
                "thu bay",
                "chu nhat",
                "ngay",
                "thang",
                "nam",
                "phut truoc",
                "gio truoc",
                "anh:",
                "video:",
                "xem them",
                "ban quyen",
                "chia se",
                "lien he",
                "hotline",
            ]
            if any(word in name_lower for word in bad_words):
                return False
            return True

        fake_authors = [
            "vietnamnet news",
            "vietnamnet",
            "ban bien tap",
            "giam ngheo benh vuong",
            "dan tri",
            "thoi su",
            "kinh te",
        ]

        fallback_author = ""
        if author:
            author_lower = author.lower()
            if any(
                fake in author_lower for fake in fake_authors
            ) or not is_valid_author(author):
                fallback_author = author
                author = ""

        if not author:
            author_selectors = [
                response.css('a[href*="tac-gia"]::text').getall(),
                response.css('a[rel="author"]::text').getall(),
                response.css(".author-name::text").get(),
                response.css(".author-name a::text").get(),
                response.css(".detail-author::text").get(),
                response.css(".tacgia::text").get(),
                response.css(".tac-gia::text").get(),
                response.css(".post-author::text").get(),
                response.css(".article-author::text").get(),
                response.css(".author::text").get(),
                response.css('[itemprop="author"] [itemprop="name"]::text').get(),
                response.css('[rel="author"]::text').get(),
                response.css('p[style*="text-align:right"] strong::text').get(),
            ]

            for a in author_selectors:
                if isinstance(a, list):
                    a = " ".join([t.strip() for t in a if t and t.strip()])
                if a and isinstance(a, str) and a.strip() and a.strip() != "Unknown":
                    clean_a = a.split("•")[0].strip()
                    clean_a = re.sub(
                        r"(?i)^(?:Nguon|Theo|Source|Anh va bai|Bai va anh|Anh|Tong hop)\s*:?\s*",
                        "",
                        clean_a,
                    ).strip()
                    if is_valid_author(clean_a):
                        author = clean_a
                        break

        if not author or author == "Unknown":
            main_content = response.css(
                'div[class*="content"], article, div[id*="content"], .post-body, .detail-content'
            )
            target_area = main_content if main_content else response
            bottom_nodes = target_area.xpath(
                './/p | .//div[contains(@class, "author") or contains(@class, "right") or contains(@style, "right")]'
            )

            if bottom_nodes:
                for node in reversed(bottom_nodes[-15:]):
                    full_text = node.xpath("normalize-space(.)").get()
                    if not full_text:
                        continue
                    clean_text = (
                        full_text.replace('"', "")
                        .replace("“", "")
                        .replace("”", "")
                        .strip()
                    )
                    if len(clean_text) < 2 or len(clean_text) > 100:
                        continue
                    match_source = re.search(
                        r"(?i)(?:Nguon|Theo|Source)\s*:?\s*(.+)", clean_text
                    )
                    if match_source:
                        candidate = match_source.group(1).strip()
                        if is_valid_author(candidate):
                            author = candidate
                            break

        if not author or author == "Unknown":
            if fallback_author:
                author = fallback_author
            else:
                meta_author = (
                    response.css('meta[name="author"]::attr(content)').get()
                    or response.css(
                        'meta[property="article:author"]::attr(content)'
                    ).get()
                )
                if meta_author and is_valid_author(meta_author.strip()):
                    author = meta_author.strip()

        author = author if author else "Unknown"

        p_date = None
        raw_dates = [
            response.css(
                'meta[property="article:published_time"]::attr(content)'
            ).get(),
            response.css("time::attr(datetime)").get(),
            response.css("time::text").get(),
            response.css('meta[name="pubdate"]::attr(content)').get(),
            response.css(".publish-date::text").get(),
            response.css(".bread-crumb-detail__time::text").get(),
            response.css('[data-role="publishdate"]::text').get(),
            response.css(".detail-time div::text").get(),
            response.css(".detail-time::text").get(),
            response.css("span.date::text").get(),
        ]

        for raw_date in raw_dates:
            if not raw_date or not raw_date.strip():
                continue
            clean_date = re.sub(r"\s+", " ", raw_date).replace("\xa0", " ").strip()
            try:
                match_iso = re.search(
                    r"(\d{4})-(\d{1,2})-(\d{1,2})(?:T|\s+)(\d{1,2}):(\d{1,2})",
                    clean_date,
                )
                if match_iso:
                    y, m, d, h, minute = match_iso.groups()
                    p_date = datetime(int(y), int(m), int(d), int(h), int(minute))
                    break
                match_vn = re.search(
                    r"(\d{1,2})[/-](\d{1,2})[/-](\d{4}).*?(\d{1,2}):(\d{1,2})",
                    clean_date,
                )
                if match_vn:
                    d, m, y, h, minute = match_vn.groups()
                    p_date = datetime(int(y), int(m), int(d), int(h), int(minute))
                    break
                match_date = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", clean_date)
                if match_date:
                    d, m, y = match_date.groups()
                    p_date = datetime(int(y), int(m), int(d))
                    break
            except Exception:
                continue

        if not p_date:
            p_date = article.publish_date

        publish_date = p_date.strftime("%Y-%m-%d %H:%M:%S") if p_date else "Unknown"

        yield {
            "title": article.title.strip(),
            "content": article.text.strip(),
            "url": response.url,
            "source": urlparse(response.url).netloc,
            "author": author,
            "publish_date": publish_date,
        }
