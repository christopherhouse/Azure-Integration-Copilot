# Task 001 — Monorepo Scaffold

## Title

Set up the monorepo directory structure, tooling, and development environment.

## Objective

Create a working monorepo with a Python backend (FastAPI), a Next.js frontend, and shared configuration so that all subsequent tasks have a consistent foundation to build on.

## Why This Task Exists

Every subsequent task depends on a consistent project structure, dependency management, and development workflow. Without a proper scaffold, each task would need to make structural decisions, leading to inconsistency and rework.

## In Scope

- Monorepo directory structure matching the repository structure in the project spec
- Python 3.13 project setup with UV (pyproject.toml, lock file)
- Next.js project setup with TypeScript, Tailwind, shadcn/ui
- Shared linting and formatting configuration (ruff for Python, ESLint + Prettier for TypeScript)
- Docker Compose for local development (backend + frontend)
- Dockerfiles for backend and frontend
- `.gitignore` updates
- Basic README updates
- Makefile or `justfile` with common commands

## Out of Scope

- Application code (routes, services, models)
- Azure infrastructure
- CI/CD workflows beyond a basic skeleton
- Database setup or connections
- Authentication
- Worker services (created in later tasks)

## Dependencies

None. This is the first task.

## Files/Directories Expected to Be Created or Modified

```
src/
├── backend/
│   ├── pyproject.toml
│   ├── main.py                    # Minimal FastAPI app with health endpoint
│   ├── config.py                  # Empty config module
│   ├── middleware/
│   │   └── __init__.py
│   ├── shared/
│   │   └── __init__.py
│   ├── domains/
│   │   └── __init__.py
│   └── Dockerfile
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── src/
│   │   └── app/
│   │       ├── layout.tsx         # Root layout
│   │       └── page.tsx           # Placeholder home page
│   └── Dockerfile
docker-compose.yml                 # Backend + frontend services
Makefile                           # Common commands (dev, build, lint, test)
.gitignore                         # Updated for Python + Node
```

## Implementation Notes

### Python Backend

1. Use UV for dependency management. Initialize with:
   ```bash
   cd src/backend
   uv init --name integration-copilot-api
   ```
2. Add initial dependencies to `pyproject.toml`:
   - `fastapi[standard]`
   - `uvicorn[standard]`
   - `pydantic>=2.0`
   - `azure-identity`
   - `azure-cosmos`
   - `azure-storage-blob`
   - `structlog` (for structured logging)
3. Add dev dependencies:
   - `ruff`
   - `pytest`
   - `pytest-asyncio`
   - `httpx` (for testing FastAPI)
4. Configure `ruff` in `pyproject.toml`:
   ```toml
   [tool.ruff]
   target-version = "py313"
   line-length = 120
   
   [tool.ruff.lint]
   select = ["E", "F", "I", "UP", "B"]
   ```
5. Create a minimal `main.py`:
   ```python
   from fastapi import FastAPI

   app = FastAPI(title="Integrisight.ai API", version="0.1.0")

   @app.get("/api/v1/health")
   async def health():
       return {"status": "ok"}
   ```

### Next.js Frontend

1. Initialize with:
   ```bash
   cd src/frontend
   npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
   ```
2. Install shadcn/ui:
   ```bash
   npx shadcn@latest init
   ```
3. Create a minimal root layout and home page.
4. Configure ESLint and Prettier.

### Docker Compose

```yaml
services:
  backend:
    build:
      context: ./src/backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development

  frontend:
    build:
      context: ./src/frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Makefile

Include targets:
- `dev-backend`: Run backend with hot reload
- `dev-frontend`: Run frontend with hot reload
- `lint`: Run linters for both projects
- `test`: Run tests for both projects
- `build`: Build Docker images
- `up`: Docker compose up

## Acceptance Criteria

- [ ] `cd src/backend && uv sync` installs Python dependencies without errors
- [ ] `cd src/frontend && npm install` installs Node dependencies without errors
- [ ] `cd src/backend && uv run uvicorn main:app --reload` starts the API server
- [ ] `cd src/frontend && npm run dev` starts the Next.js dev server
- [ ] `curl http://localhost:8000/api/v1/health` returns `{"status": "ok"}`
- [ ] `http://localhost:3000` loads the frontend in a browser
- [ ] `cd src/backend && uv run ruff check .` passes
- [ ] `cd src/frontend && npm run lint` passes
- [ ] `docker compose up --build` starts both services
- [ ] Directory structure matches the expected layout

## Definition of Done

- All files listed above exist with appropriate content.
- Both projects build and run independently.
- Docker Compose brings up both services.
- Linting passes for both projects.
- A developer (or coding agent) can start the next task without additional setup.

## Risks / Gotchas

- **UV version**: Ensure UV is installed and supports Python 3.13. Check with `uv --version`.
- **Next.js version**: Use `@latest` to get the current stable version. Pin in `package.json` after creation.
- **shadcn/ui init**: May prompt for configuration choices. Accept defaults (New York style, CSS variables).
- **Port conflicts**: Ensure ports 3000 and 8000 are available locally.
- **Docker build context**: Dockerfiles must be relative to their respective `src/` subdirectories.

## Suggested Validation Steps

1. Run `uv sync` in `src/backend/` and verify no errors.
2. Run `npm install` in `src/frontend/` and verify no errors.
3. Start the backend: `uv run uvicorn main:app --port 8000` and hit the health endpoint.
4. Start the frontend: `npm run dev` and load `localhost:3000` in a browser.
5. Run linters for both projects.
6. Run `docker compose up --build` and verify both containers start.
7. Verify `.gitignore` excludes `node_modules/`, `__pycache__/`, `.venv/`, `.next/`.
