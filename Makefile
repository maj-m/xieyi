.PHONY: up down logs migrate test lint format typecheck
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f backend
migrate:
	cd backend && uv run alembic upgrade head
test:
	cd backend && uv run pytest
lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
typecheck:
	cd backend && uv run mypy app
