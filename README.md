# RubricLab

Rubric-driven evaluation harness for LLM agents. Point it at an agent, give it a dataset and a rubric, get structured pass/fail scores and a diff-able run history.

## Why this exists

Vibes-based testing doesn't scale: the agent works on three hand-picked examples, then quietly regresses on the fourth. Existing tools are either heavyweight SaaS observability platforms that want your data, or raw `pytest` matchers that can't grade open-ended outputs. RubricLab sits in the middle — rubric-driven LLM-as-judge scoring with a run-history UI so regressions are obvious at a glance.

## What works (M1 — scaffold)

The repository is a working monorepo with tooling configured end-to-end. No eval logic yet; that starts in M2.

- **Monorepo layout** — `apps/api` (FastAPI, Python 3.12, src layout) and `apps/web` (Next.js 14, TypeScript)
- **Python tooling** — `pyproject.toml` with `ruff` for lint/format, `pytest` with a passing smoke test
- **JavaScript tooling** — ESLint, Prettier, Tailwind CSS, shadcn/ui scaffolded (`components.json`)
- **Makefile** — `make install`, `make dev`, `make test`, `make lint`, `make format` all functional
- **Environment** — `.env.example` documents `ANTHROPIC_API_KEY`; both servers start cleanly via `make dev`

## Architecture

- **FastAPI** (`apps/api`, port 8000) — eval runner, LLM judge, SQLite persistence
- **Next.js** (`apps/web`, port 3000) — run list, case drill-down, side-by-side diff
- **SQLite** — local, single-file, zero infra
- **Claude `claude-opus-4-6`** — LLM-as-judge for rubric scoring

> SQLite persistence and the LLM judge are planned; the API and web apps are scaffold-only at M1.

## Quickstart

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
make install
make dev
```

## Development

### Prerequisites

- Python 3.12+
- Node 20+
- `make`
- Git Bash or WSL2 (on Windows — the `&` background operator in the Makefile requires a POSIX shell)

### Setup

```bash
cp .env.example .env
make install   # pip install -e "[dev]" + npm install
make test      # pytest + eslint
make dev       # FastAPI on :8000, Next.js on :3000
```

> **Note (Python src layout):** `pytest` requires an editable install to resolve the `api` package.
> Always run `make install` before `make test`, or prefix with `pip install -e ".[dev]"` inside `apps/api`.

### Lint / Format

```bash
make lint      # ruff check + eslint
make format    # ruff format + prettier
```

## Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Monorepo scaffold, tooling, CI baseline | done |
| M2 | Rubric schema (JSON), eval runner endpoint, dataset loader | planned |
| M3 | LLM-as-judge integration, per-criterion scoring, pass/fail verdict | planned |
| M4 | SQLite persistence, run history API | planned |
| M5 | Web UI — run list, case drill-down, side-by-side diff | planned |

<!-- TODO: add M6+ milestones as scope becomes clearer -->

## License

MIT — see [LICENSE](LICENSE).
