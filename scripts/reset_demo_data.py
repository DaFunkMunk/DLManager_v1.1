"""Reset and reseed demo data collections in MongoDB."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.demo_adapter import DemoAdapter  # noqa: E402

DOTENV_PATH = PROJECT_ROOT / ".env"

if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)

MONGO_URI = os.getenv("DEMO_MONGO_URI")
DB_NAME = os.getenv("DEMO_MONGO_DB", "dl_demo")

if not MONGO_URI:
    raise SystemExit("DEMO_MONGO_URI is not defined; update .env before running.")


def main() -> None:
    adapter = DemoAdapter(MONGO_URI, db_name=DB_NAME, seed=False)
    adapter.seed_if_empty(force=True)
    adapter.close()
    print("Demo data reset complete.")


if __name__ == "__main__":
    main()
