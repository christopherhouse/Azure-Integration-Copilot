.PHONY: dev-backend dev-frontend lint test build up

dev-backend:
	cd src/backend && uv run uvicorn main:app --reload --port 8000

dev-frontend:
	cd src/frontend && npm run dev

lint:
	cd src/backend && uv run ruff check .
	cd src/frontend && npm run lint

test:
	cd src/backend && uv run pytest
	cd src/frontend && npm test

build:
	docker compose build

up:
	docker compose up --build
