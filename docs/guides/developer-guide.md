# Developer Guide

This guide covers how to set up, develop, test, and run Integration Copilot locally.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **Python** | 3.13+ | Installed automatically by UV |
| **UV** | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js** | 22+ | [nodejs.org](https://nodejs.org/) |
| **npm** | 10+ | Bundled with Node.js |
| **Docker** | 24+ | [docker.com](https://www.docker.com/) |
| **Docker Compose** | v2+ | Bundled with Docker Desktop |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/christopherhouse/Azure-Integration-Copilot.git
cd Azure-Integration-Copilot

# Start both services with Docker Compose
make up
```

The backend will be available at `http://localhost:8000` and the frontend at `http://localhost:3000`.

## Project Structure

```
src/
├── backend/            # Python 3.13 FastAPI backend
│   ├── main.py         # FastAPI app with health endpoint
│   ├── config.py       # Application configuration (placeholder)
│   ├── middleware/      # HTTP middleware (placeholder)
│   ├── shared/         # Shared utilities (placeholder)
│   ├── domains/        # Domain modules (placeholder)
│   ├── pyproject.toml  # Python project config and dependencies
│   ├── uv.lock         # Locked dependency versions
│   └── Dockerfile      # Multi-stage production image
└── frontend/           # Next.js 16 TypeScript frontend
    ├── src/
    │   ├── app/        # Next.js App Router pages
    │   ├── components/ # Reusable UI components (shadcn/ui)
    │   └── lib/        # Shared utilities
    ├── package.json    # Node.js project config
    └── Dockerfile      # Multi-stage production image

tests/
├── backend/            # Python tests (pytest)
├── frontend/           # Frontend tests (Jest + React Testing Library)
└── integration/        # End-to-end tests (placeholder)
```

## Backend Development

### Setup

```bash
cd src/backend

# Install dependencies (creates .venv automatically)
uv sync

# Start the development server with hot reload
uv run uvicorn main:app --reload --port 8000
```

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check — returns `{"status": "ok"}` |

### Linting

The backend uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
cd src/backend

# Check for lint errors
uv run ruff check .

# Auto-fix lint errors
uv run ruff check . --fix

# Format code
uv run ruff format .
```

Ruff is configured in `pyproject.toml`:

- **Target**: Python 3.13
- **Line length**: 120
- **Rules**: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear)

### Testing

```bash
cd src/backend

# Run all backend tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest ../../tests/backend/test_health.py
```

Tests are located in `tests/backend/` and use:

- **pytest** — Test framework
- **pytest-asyncio** — Async test support
- **httpx** — Async HTTP client for testing FastAPI endpoints

### Adding Dependencies

```bash
cd src/backend

# Add a production dependency
uv add <package-name>

# Add a dev dependency
uv add --group dev <package-name>

# Sync dependencies after editing pyproject.toml
uv sync
```

> **Important**: Always use UV for Python dependency management. Do not use `pip` directly.

## Frontend Development

### Setup

```bash
cd src/frontend

# Install dependencies
npm install

# Start the development server with hot reload
npm run dev
```

The dev server starts at `http://localhost:3000`.

### Available Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `npm run dev` | Start development server |
| `build` | `npm run build` | Build for production |
| `start` | `npm run start` | Start production server |
| `lint` | `npm run lint` | Run ESLint |
| `test` | `npm test` | Run Jest tests |

### UI Components

The frontend uses [shadcn/ui](https://ui.shadcn.com/) with Tailwind CSS. To add a new component:

```bash
cd src/frontend
npx shadcn@latest add <component-name>
```

Components are installed to `src/components/ui/`.

### Testing

```bash
cd src/frontend

# Run all frontend tests
npm test

# Run with verbose output
npm test -- --verbose

# Run a specific test file
npm test -- --testPathPattern="page.test"
```

Tests are located in `tests/frontend/` and use:

- **Jest** — Test framework
- **React Testing Library** — Component testing utilities
- **@testing-library/jest-dom** — Custom DOM matchers

### Linting

```bash
cd src/frontend
npm run lint
```

ESLint is configured via `eslint.config.mjs` with the Next.js ESLint config.

## Docker Development

### Build and Run Both Services

```bash
# Build and start both services
docker compose up --build

# Run in detached mode
docker compose up --build -d

# Stop services
docker compose down
```

### Build Individual Services

```bash
# Backend only
docker compose build backend
docker compose up backend

# Frontend only
docker compose build frontend
docker compose up frontend
```

### Service Ports

| Service | Port | URL |
|---------|------|-----|
| Backend | 8000 | `http://localhost:8000` |
| Frontend | 3000 | `http://localhost:3000` |

## Makefile Targets

The root `Makefile` provides convenient shortcuts:

| Target | Description |
|--------|-------------|
| `make dev-backend` | Start backend dev server with hot reload |
| `make dev-frontend` | Start frontend dev server with hot reload |
| `make lint` | Run linters for both backend and frontend |
| `make test` | Run tests for both backend and frontend |
| `make build` | Build Docker images for both services |
| `make up` | Build and start both services with Docker Compose |

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend framework | FastAPI | Latest |
| Backend runtime | Python | 3.13 |
| Backend package manager | UV | Latest |
| Backend linter | Ruff | Latest |
| Frontend framework | Next.js | 16 |
| Frontend language | TypeScript | 5 |
| Frontend styling | Tailwind CSS | 4 |
| Frontend components | shadcn/ui | Latest |
| Frontend testing | Jest + React Testing Library | 29 |
| Backend testing | pytest + httpx | Latest |
| Containerization | Docker + Docker Compose | Latest |
