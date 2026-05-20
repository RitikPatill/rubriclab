# RubricLab

Rubric-driven evaluation harness for LLM agents. Point it at an agent, give it a dataset and a rubric, get structured pass/fail scores and a diff-able run history.

## Why this exists

Vibes-based testing doesn't scale: the agent works on three hand-picked examples, then quietly regresses on the fourth. Existing tools are either heavyweight SaaS observability platforms that want your data, or raw `pytest` matchers that can't grade open-ended outputs. RubricLab sits in the middle — rubric-driven LLM-as-judge scoring with a run-history UI so regressions are obvious at a glance.

## What works (M6 — web UI: runs + run detail)

- **Runs list** — `GET /` lists all evaluation runs with status badges (pending / running / completed / failed), pass-rate (`N / N (xx%)`), start time, and duration. Empty-state shows the POST endpoint snippet.
- **Run detail** — `GET /runs/[id]` shows run metadata (suite, agent version, git SHA, timing, pass rate), a live SSE progress bar while the run is `"running"`, and a per-case table with one column per rubric criterion showing `<ScoreCell />` scores.
- **Case trace viewer** — `GET /runs/[id]/cases/[caseId]` renders the agent output, tool-call trace event-by-event (TOOL / RESULT / text / error badges), per-criterion judge scores with reasoning, and deterministic check results.
- **Dark mode** — `next-themes` wraps the app with `defaultTheme="system"`; a sun/moon toggle button in the nav bar switches themes. All CSS variables defined in `globals.css` handle light and dark palettes automatically.
- **CORS** — FastAPI now allows `http://localhost:3000` so the browser can call the API directly.
- **Typed API layer** — [`apps/web/src/lib/types.ts`](apps/web/src/lib/types.ts) mirrors all API schemas; [`apps/web/src/lib/api.ts`](apps/web/src/lib/api.ts) provides typed `listRuns()`, `getRun()`, and `listSuites()` wrappers used by server components.
- **shadcn/ui components** — Badge, Table, Card, Progress, Separator, Button installed and used throughout.

## What works (M5 — REST API + run streaming)

- **Suite CRUD** — `POST /suites` creates a (rubric, dataset) pair; `GET /suites` and `GET /suites/{id}` list and fetch them.
- **Run management** — `POST /suites/{suite_id}/runs` returns 202 Accepted immediately (run ID + `"pending"` status) and executes the eval in a background thread. Requires `agent_url` and optional `agent_version` in the request body.
- **Live SSE stream** — `GET /runs/{run_id}/stream` emits `progress` events as each case completes and a final `done` event when the run finishes, using Server-Sent Events (`text/event-stream`).
- **Typed response models** — [`apps/api/src/api/schemas/api.py`](apps/api/src/api/schemas/api.py) defines `SuiteCreate`, `SuiteResponse`, `RunStartRequest`, `RunStartResponse`, `RunSummary`, `RunDetail`, and `CaseResultResponse`; every endpoint declares a Pydantic `response_model` and FastAPI auto-generates OpenAPI docs at `/docs`.
- **Integration tests** — `apps/api/tests/test_api.py` covers suite CRUD (including 404 handling), the start-run → poll → assert-scores flow (with a mock runner), and SSE endpoint sanity and 404 handling (5 tests). `apps/api/tests/conftest.py` provides a session-scoped DB initialisation fixture shared across all test modules.

## What works (M4 — eval runner + LLM judge)

- **Eval runner** — [`apps/api/src/api/runner.py`](apps/api/src/api/runner.py): iterates every test case, invokes the agent adapter, runs deterministic checks, calls the LLM judge, and persists all results to SQLite. Agent exceptions are caught per-case so one bad case never aborts a run.
- **LLM-as-judge** — [`apps/api/src/api/judge.py`](apps/api/src/api/judge.py): builds a structured prompt with the rubric, test-case input, agent output, and execution trace; calls Claude and parses the JSON response into per-criterion `CriterionScore` objects. **Self-consistency mode** — set `JudgeConfig(samples=N)` to sample the judge N times and aggregate (median for scale criteria, majority vote for bool criteria).
- **Deterministic checks** — [`apps/api/src/api/checks.py`](apps/api/src/api/checks.py): four check types that run alongside the LLM judge and are included in the pass/fail verdict:
  - `exact_match` — stripped string equality
  - `regex` — `re.search` against agent output
  - `json_schema` — validates agent output JSON against a JSON Schema
  - tool-call assertions via `expected_tool_calls` in the test case (inspects the execution trace)
- **SQLite persistence** — [`apps/api/src/api/models.py`](apps/api/src/api/models.py) defines `Suite`, `Run`, and `CaseResult`; [`db.py`](apps/api/src/api/db.py) manages the engine and session. Every run is immutable; rows are committed case-by-case so partial results survive a crash. Each run is tagged with `git_sha` and `agent_version`.
- **Pass/fail verdict** — a case passes when every deterministic check passes AND every LLM criterion passes its threshold: scale `score >= ceil((min+max)/2)`; bool `score == True`; inverted bool `score == False`.
- **Run history API** — `GET /runs` lists all runs (newest first); `GET /runs/{id}` returns the full run with all `CaseResult` rows (scores, trace, deterministic checks).
- **Tests** — 91 tests total (36 pre-existing + 22 checks + 21 judge + 12 runner), all green. M5 adds 5 more integration tests.

### M3 — agent adapter + sample agent (also done)

- **`AgentAdapter` protocol** — `run(input: str) -> AgentResult` contract. `AgentResult` carries `output: str` and `trace: list[TraceEvent]`. `TraceEvent` records `tool_call`, `tool_result`, `text`, or `error` events with ISO timestamps. See [`apps/api/src/api/adapters/`](apps/api/src/api/adapters/).
- **`InProcessAdapter`** — wraps any Python callable `fn(input) -> AgentResult | str` for in-process evaluation. Normalises plain `str` returns automatically.
- **`HttpAdapter`** — POSTs `{"input": "..."}` to any HTTP endpoint and validates the JSON response as `AgentResult`; supports custom headers and configurable timeout.
- **Sample support agent** — [`examples/support-agent/agent.py`](examples/support-agent/agent.py) uses the Anthropic SDK with three fake tools (`kb_search`, `order_lookup`, `escalate_to_human`). All tool responses are deterministic stubs — no real integrations needed for demos. Requires `ANTHROPIC_API_KEY` only for the Claude API call.

    ```bash
    # Run the sample agent from the repo root
    cd apps/api && python -m pip install -e ".[dev]"
    ANTHROPIC_API_KEY=sk-... python ../../examples/support-agent/agent.py "Where is my order #12345?"
    ```

### M2 — rubric + dataset schemas (also done)

- **Rubric DSL** — YAML files with named criteria of type `scale` (min/max range) or `bool` (pass/fail, optionally `invert`ed). Each criterion has an `id`, `description`, optional `weight`, and optional `invert` flag. See [`examples/support-agent/rubric.yaml`](examples/support-agent/rubric.yaml).
- **Dataset format** — JSONL files; one test case per line with `id`, `input`, `expected_behavior`, optional `expected_tool_calls`, optional `checks`, and `tags`. See [`examples/support-agent/dataset.jsonl`](examples/support-agent/dataset.jsonl).
- **Pydantic loaders** — `load_rubric(path)` and `load_dataset(path)` validate inputs, wrap errors with line numbers, and detect duplicates.
- **15-case example dataset** — covers password reset, billing disputes, refunds, shipping, product compatibility, security escalations, and technical support.

### M1 — scaffold (also done)

- **Monorepo layout** — `apps/api` (FastAPI, Python 3.11+, src layout) and `apps/web` (Next.js 14, TypeScript)
- **Python tooling** — `pyproject.toml` with `ruff` for lint/format, `pytest` with a passing smoke test
- **JavaScript tooling** — ESLint, Prettier, Tailwind CSS, shadcn/ui scaffolded (`components.json`)
- **Makefile** — `make install`, `make dev`, `make test`, `make lint`, `make format` all functional
- **Environment** — `.env.example` documents `ANTHROPIC_API_KEY`; both servers start cleanly via `make dev`

## Architecture

- **FastAPI** (`apps/api`, port 8000) — eval runner, LLM judge, SQLite persistence
- **Next.js** (`apps/web`, port 3000) — run list, run detail, case trace viewer
- **SQLite** — local, single-file, zero infra
- **Claude** — LLM-as-judge for rubric scoring (configurable model, default `claude-haiku-4-5-20251001`)

> As of M6, both the API and web UI are live. Open `http://localhost:3000` for the runs list. OpenAPI docs at `http://localhost:8000/docs`.

## Quickstart

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
make install
make dev
```

## Development

### Prerequisites

- Python 3.11+
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
| M2 | Rubric + dataset schemas, Pydantic loaders, example files | done |
| M3 | AgentAdapter protocol, InProcessAdapter, HttpAdapter, sample support agent | done |
| M4 | Eval runner, deterministic checks, LLM-as-judge, self-consistency, SQLite persistence | done |
| M5 | Full run management API (POST /runs, suite CRUD, SSE streaming) | done |
| M6 | Web UI — run list, run detail, case trace viewer, dark mode | done |

<!-- TODO: add M6+ milestones as scope becomes clearer -->

## License

MIT — see [LICENSE](LICENSE).
