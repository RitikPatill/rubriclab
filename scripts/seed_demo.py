"""Seed the demo database with two evaluation runs.

Run from the repo root:
    python scripts/seed_demo.py

The script creates one Suite (pointing at the bundled support-agent example),
then runs the eval twice:
  - v1-basic   : escalation-happy prompt that skips KB search
  - v2-improved: the agent's real SYSTEM_PROMPT (KB-first, escalate only when needed)

After both runs complete the comparison URL is printed.
"""

from __future__ import annotations

import pathlib
import sys

# ---------------------------------------------------------------------------
# Path setup — must happen before any local imports
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "examples" / "support-agent"))

# ---------------------------------------------------------------------------
# Imports (all local, no FastAPI / uvicorn)
# ---------------------------------------------------------------------------

import uuid  # noqa: E402

from api.adapters.inprocess import InProcessAdapter  # noqa: E402
from api.db import SessionLocal, init_db  # noqa: E402
from api.models import Suite  # noqa: E402
from api.runner import run_eval  # noqa: E402
from api.schemas.dataset import load_dataset  # noqa: E402
from api.schemas.rubric import load_rubric  # noqa: E402

# Import make_run and the default SYSTEM_PROMPT from the bundled agent.
# The agent module itself adds the api package to sys.path when run as __main__,
# but here we've already done that above so the import is clean.
from agent import SYSTEM_PROMPT, make_run  # noqa: E402

# ---------------------------------------------------------------------------
# Prompt variants
# ---------------------------------------------------------------------------

PROMPT_V1 = (
    "You are a customer support agent. Be brief. "
    "If you are not certain of the answer, escalate to a human immediately."
)

PROMPT_V2 = SYSTEM_PROMPT  # KB-first, escalate only when genuinely needed

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EXAMPLE_DIR = ROOT / "examples" / "support-agent"
RUBRIC_PATH = str(EXAMPLE_DIR / "rubric.yaml")
DATASET_PATH = str(EXAMPLE_DIR / "dataset.jsonl")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Initialising database …")
    init_db()
    db = SessionLocal()

    try:
        # ── Suite ────────────────────────────────────────────────────────────
        suite = Suite(
            id=str(uuid.uuid4()),
            name="Support Agent Demo",
            rubric_path=RUBRIC_PATH,
            dataset_path=DATASET_PATH,
        )
        db.add(suite)
        db.commit()
        db.refresh(suite)

        rubric = load_rubric(RUBRIC_PATH)
        dataset = load_dataset(DATASET_PATH)

        # ── Run 1 — v1-basic ─────────────────────────────────────────────────
        print(f"\nRunning v1-basic ({len(dataset)} cases) …")
        run1 = run_eval(
            suite=suite,
            rubric=rubric,
            dataset=dataset,
            adapter=InProcessAdapter(make_run(PROMPT_V1)),
            db=db,
            agent_version="v1-basic",
        )
        print(f"  v1-basic  passed={run1.passed_cases}/{run1.total_cases}")

        # ── Run 2 — v2-improved ───────────────────────────────────────────────
        print(f"\nRunning v2-improved ({len(dataset)} cases) …")
        run2 = run_eval(
            suite=suite,
            rubric=rubric,
            dataset=dataset,
            adapter=InProcessAdapter(make_run(PROMPT_V2)),
            db=db,
            agent_version="v2-improved",
        )
        print(f"  v2-improved passed={run2.passed_cases}/{run2.total_cases}")

    finally:
        db.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅  Done — 2 runs in database")
    print(f"   Suite:    {suite.id}")
    print(f"   Run 1:    {run1.id}  (v1-basic)     pass={run1.passed_cases}/{run1.total_cases}")
    print(f"   Run 2:    {run2.id}  (v2-improved)  pass={run2.passed_cases}/{run2.total_cases}")
    print()
    print("Open in browser:")
    print("  Runs list:   http://localhost:3000")
    print(f"  Comparison:  http://localhost:3000/compare?a={run1.id}&b={run2.id}")


if __name__ == "__main__":
    main()
