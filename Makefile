.PHONY: run dev install test smoke docker docker-up docker-down

install:
	uv sync

run:
	uv run uvicorn main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

smoke:
	@echo "=== Health ==="
	curl -s http://localhost:8000/health | python3 -m json.tool
	@echo "\n=== Create project ==="
	curl -s -X POST http://localhost:8000/projects \
	  -H "Content-Type: application/json" \
	  -d '{"name":"TestProduct","category":"test tool","competitors":["Competitor1"]}'  | python3 -m json.tool

docker:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
