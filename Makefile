.PHONY: help setup up down restart crawl full run-crawl run-etl run-vectorize clean test-interactive test-gen

PYTHON = venv/bin/python
SCRAPY = venv/bin/scrapy
DOCKER_COMPOSE = docker-compose
UVICORN = venv/bin/uvicorn

setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
	@echo "[SETUP] Environment created."

up:
	$(DOCKER_COMPOSE) up -d
	@echo "[DOCKER] Postgres + Kafka started."

down:
	$(DOCKER_COMPOSE) down

restart: down up

full:
	@echo "[PIPELINE] Running full pipeline: Crawl -> ETL -> Vectorize..."
	$(PYTHON) main.py --mode full

auto:
	@echo "[PIPELINE] Running auto mode (3 runs/day)..."
	$(PYTHON) main.py --mode auto

run-crawl:
	$(PYTHON) main.py --mode crawl

run-etl:
	$(PYTHON) main.py --mode etl

run-vectorize:
	$(PYTHON) main.py --mode vectorize

crawl:
	export PYTHONPATH=. && $(SCRAPY) crawl news_rag_spider

test-interactive:
	PYTHONPATH=. $(PYTHON) -m tests.search.test_interactive

test-gen:
	PYTHONPATH=. $(PYTHON) -m tests.search.test_generator

run-fastapi:
	$(UVICORN) app.api:app --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "[CLEAN] Done."
