.PHONY: help setup backend frontend venv crawl migrate clean

PYTHON = venv/bin/python3
UVICORN = venv/bin/python3 -m uvicorn
SCRAPY = venv/bin/scrapy

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: venv data/config ## First-time project setup

venv: ## Create virtualenv and install deps
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

backend: ## Start FastAPI backend (port 8000)
	$(UVICORN) app.api:app --reload --port 8000

frontend: ## Start Next.js frontend (port 3000)
	cd frontend && npm run dev

crawl: ## Crawl news articles into data/articles.json
	PYTHONPATH=. $(SCRAPY) crawl news_rag_spider -s "ITEM_PIPELINES={}" -o data/articles.json

migrate: ## Migrate articles.json -> RDS star-schema
	$(PYTHON) scripts/init_db/migrate_to_star_schema.py

vectorize: ## Embed chunks -> pgvector
	$(PYTHON) -m vectorize.vectorize

clean: ## Remove caches
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .next/ data/ .pytest_cache

data/config:
	mkdir -p data
	@echo "Ready"