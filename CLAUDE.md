# CLAUDE.md

## Project Overview

Pi Couch Hound — Raspberry Pi-powered dog detector that monitors a couch and triggers configurable actions when a dog is detected. Python backend (FastAPI) + React TypeScript frontend (Vite).

## Repository Structure

- `couch_hound/` — Python backend package
  - `api/` — FastAPI app factory, route modules, Pydantic schemas
  - `actions/` — Action executor base class and implementations
  - `config.py` — YAML config loader/saver with Pydantic validation
  - `main.py` — Entry point (uvicorn runner)
- `frontend/` — React TypeScript SPA (Vite, Tailwind, TanStack Query, Zustand)
- `tests/` — pytest test suite
- `SPEC.md` — Full technical specification (source of truth for API contracts, config schema, architecture)

## Development Commands

### Backend

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check couch_hound/ tests/

# Format check
ruff format --check couch_hound/ tests/

# Auto-format
ruff format couch_hound/ tests/

# Type check
mypy couch_hound/

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=couch_hound --cov-report=term-missing

# Run dev server
python -m uvicorn couch_hound.api.app:create_app --factory --port 8080 --reload
```

### Frontend

```bash
cd frontend
npm ci
npm run lint
npm run type-check
npm test
npm run build
```

## CI

Two GitHub Actions workflows (`.github/workflows/`):
- **backend.yml**: ruff check, ruff format --check, mypy, pytest with coverage (Python 3.12)
- **frontend.yml**: eslint, tsc, vitest, vite build (Node 20)

Both trigger on pushes and PRs to main/master for their respective paths.

## Code Style

- Python >=3.12, line length 100
- Ruff for linting and formatting (rules: E, F, I, N, W, UP)
- Mypy strict mode with pydantic plugin
- pytest with asyncio_mode = "auto"
- Always run `ruff check` and `ruff format --check` before committing
