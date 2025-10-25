# Makefile for common developer tasks (Docker-first)
.PHONY: build up down logs renormalize get-tesseract test

build:
	docker compose build --no-cache

up:
	docker compose up -d --remove-orphans

down:
	docker compose down

logs:
	docker compose logs -f

restart: down up

renormalize:
	python backend/re_normalize_db.py

get-tesseract-linux:
	./scripts/get_tesseract.sh backend/tools/tesseract

get-tesseract-windows:
	powershell -ExecutionPolicy Bypass -File scripts/get_tesseract.ps1 -Dest backend\\tools\\tesseract

# quick smoke test: ensure backend responds
test:
	@echo "Testing backend /api/v1/documents..."
	curl -sSf http://localhost:8000/api/v1/documents | jq '.["documents"] | length' || echo "Backend test failed"
