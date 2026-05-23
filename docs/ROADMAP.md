# Roadmap

## Shipped

| Milestone | Scope |
|-----------|-------|
| M1 | Monorepo scaffold, tooling, CI baseline |
| M2 | Rubric + dataset schemas, Pydantic loaders, example files |
| M3 | AgentAdapter protocol, InProcessAdapter, HttpAdapter, sample support agent |
| M4 | Eval runner, deterministic checks, LLM-as-judge, self-consistency, SQLite persistence |
| M5 | Full run management API (POST /runs, suite CRUD, SSE streaming) |
| M6 | Web UI — run list, run detail, case trace viewer, dark mode |
| M7 | Run comparison (side-by-side diff), in-UI rubric editor, clone rubric |
| M8 | Demo script, seed two runs, `make demo`, screenshot + GIF placeholders |
| M9 | Polish: README, architecture docs, roadmap, CONTRIBUTING, GitHub Actions CI |

## Near-term (good first issues)

- Replace placeholder `docs/screenshot.png` and `docs/demo.gif` with live captures from `make demo`.
- `make ci` target that mirrors the GitHub Actions workflow locally.
- Configurable judge model per-suite (stored in Suite row, not just env var).

## Medium-term

- **Hosted judge option** — allow a `JUDGE_ENDPOINT` env var to point at a self-hosted or OpenAI-compatible model so the tool is not locked to Anthropic.
- **Dataset import from production traces** — a `rubriclab import` CLI that reads OpenTelemetry / LangSmith / Langfuse trace exports and converts them to JSONL test cases.
- **Export** — `GET /runs/{id}/export.csv` and `GET /runs/{id}/export.json` for downstream analysis in notebooks.
- **Metric history charts** — sparklines per rubric criterion over time in the runs list UI.

## Long-term

- **Multi-tenant** — per-user namespacing, optional auth layer (JWT), shared read-only run links.
- **Async agent adapter** — native `async def run(input) -> AgentResult` support without thread wrapping.
- **Rubric versioning** — track rubric mutations in the DB so score changes can be attributed to rubric edits vs. agent changes.
- **Dataset generation** — LLM-assisted expansion of a seed dataset into edge-case variations.
