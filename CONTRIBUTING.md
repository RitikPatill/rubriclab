# Contributing

## Prerequisites

- Python 3.11+
- Node 20+
- `make`
- Git Bash or WSL2 on Windows

## Setup

```bash
git clone <repo> && cd rubriclab
cp .env.example .env   # set ANTHROPIC_API_KEY
make install
make test              # should be all green
```

## Project layout

```
apps/api/       FastAPI backend (Python)
  src/api/      package root — runner, judge, checks, adapters, models
  tests/        pytest test suite

apps/web/       Next.js frontend (TypeScript)
  src/          App Router pages + shadcn/ui components
  src/lib/      typed API client and shared types

examples/       sample support-agent (rubric, dataset, agent.py)
scripts/        demo seed script, record_demo.sh
docs/           ARCHITECTURE.md, ROADMAP.md, screenshot, demo GIF
```

## Running tests

```bash
# Python (from repo root)
cd apps/api && pytest -v

# JavaScript (lint only — no JS test suite yet)
cd apps/web && npm run lint
```

> **Note:** Python tests mock all Anthropic API calls via `respx`. No real API key is required for `make test`.
>
> `pytest` resolves the `api` package via an editable install. If you see `ModuleNotFoundError: No module named 'api'`, run `pip install -e ".[dev]"` inside `apps/api` first.

## Code style

- **Python** — `ruff check . && ruff format --check .` (enforced by CI)
- **TypeScript** — `eslint` + `prettier` (enforced by CI)

Run `make format` to auto-fix before committing.

## Submitting a PR

1. Branch from `main`.
2. Keep PRs small and focused (one milestone of work).
3. `make test` must pass locally before opening a PR.
4. Add or update tests for any changed behaviour.
5. Update `docs/ARCHITECTURE.md` if you change data flow or add components.
