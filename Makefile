.PHONY: dev dev-api dev-web install test lint format demo

dev:
	(cd apps/web && npm run dev) & cd apps/api && uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

dev-api:
	cd apps/api && uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd apps/web && npm run dev

install:
	cd apps/api && pip install -e ".[dev]"
	cd apps/web && npm install

test:
	cd apps/api && pytest
	cd apps/web && npm run lint

lint:
	cd apps/api && ruff check .
	cd apps/web && npm run lint

format:
	cd apps/api && ruff format .
	cd apps/web && npm run format

demo:
	bash scripts/record_demo.sh
