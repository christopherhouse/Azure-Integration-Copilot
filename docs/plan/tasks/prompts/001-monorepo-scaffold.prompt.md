# Prompt — Execute Task 001: Monorepo Scaffold

You are an expert software engineer. Execute the following task to set up the Integrisight.ai monorepo.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/001-monorepo-scaffold.md`
- **Product charter**: `docs/plan/00-product-charter.md`
- **System architecture**: `docs/plan/01-system-architecture.md`

## What You Must Do

Set up the monorepo directory structure, tooling, and development environment for Integrisight.ai — a multitenant SaaS application with a Python 3.13 backend (FastAPI) and a Next.js frontend (TypeScript).

### Step 1 — Python Backend Setup

1. Navigate to `src/backend/`.
2. Initialize a Python project using UV:
   ```bash
   uv init --name integration-copilot-api
   ```
3. Add production dependencies to `pyproject.toml`: `fastapi[standard]`, `uvicorn[standard]`, `pydantic>=2.0`, `azure-identity`, `azure-cosmos`, `azure-storage-blob`, `structlog`.
4. Add dev dependencies: `ruff`, `pytest`, `pytest-asyncio`, `httpx`.
5. Configure `ruff` in `pyproject.toml` with `target-version = "py313"`, `line-length = 120`, and lint rules `["E", "F", "I", "UP", "B"]`.
6. Create a minimal `main.py` with a FastAPI app and a `GET /api/v1/health` endpoint that returns `{"status": "ok"}`.
7. Create empty placeholder modules: `config.py`, `middleware/__init__.py`, `shared/__init__.py`, `domains/__init__.py`.
8. Create a `Dockerfile` for the backend (Python 3.13 base, UV install, uvicorn entrypoint).
9. Run `uv sync` and verify it succeeds.
10. Run `uv run ruff check .` and verify it passes.

### Step 2 — Next.js Frontend Setup

1. Navigate to `src/frontend/`.
2. Initialize the Next.js project:
   ```bash
   npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
   ```
3. Initialize shadcn/ui:
   ```bash
   npx shadcn@latest init
   ```
   Accept defaults (New York style, CSS variables).
4. Create a minimal root layout (`src/app/layout.tsx`) and home page (`src/app/page.tsx`).
5. Create a `Dockerfile` for the frontend (Node base, npm install, next build, next start).
6. Run `npm install` and verify it succeeds.
7. Run `npm run lint` and verify it passes.

### Step 3 — Monorepo Tooling

1. Create a `docker-compose.yml` at the repo root with `backend` and `frontend` services:
   - Backend: build from `./src/backend`, expose port 8000, set `ENVIRONMENT=development`.
   - Frontend: build from `./src/frontend`, expose port 3000, set `NEXT_PUBLIC_API_URL=http://localhost:8000`.
2. Create a `Makefile` at the repo root with targets: `dev-backend`, `dev-frontend`, `lint`, `test`, `build`, `up`.
3. Update `.gitignore` to include: `node_modules/`, `__pycache__/`, `.venv/`, `.next/`, `.env`, `*.pyc`, `.ruff_cache/`.

### Step 4 — Validation

Run these checks and fix any issues:

1. `cd src/backend && uv sync` — must succeed
2. `cd src/backend && uv run uvicorn main:app --port 8000` — must start, then `curl http://localhost:8000/api/v1/health` must return `{"status": "ok"}`
3. `cd src/frontend && npm install && npm run dev` — must start at localhost:3000
4. `cd src/backend && uv run ruff check .` — must pass
5. `cd src/frontend && npm run lint` — must pass
6. `docker compose up --build` — both containers must start
7. Verify directory structure matches the layout in the task spec

## Constraints

- Python 3.13 only.
- Use UV for Python dependency management — do not use pip directly.
- Use the Next.js App Router (not Pages Router).
- Do not write any application code beyond the health endpoint and placeholder pages.
- Do not create Azure infrastructure or CI/CD workflows.
- Do not create worker services.

## Done When

- Both projects build and run independently.
- Docker Compose brings up both services.
- Linting passes for both projects.
- The directory structure matches the spec.
- A developer or coding agent can start task 002 without additional setup.
