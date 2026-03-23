from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.run_daily import run_daily_job
from src.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate all current spin-off company chart pairs and send them to Telegram immediately."
    )
    parser.add_argument("--config", help="Optional path to a settings YAML file.", default=None)
    parser.add_argument("--skip-refresh", action="store_true", help="Use the stored universe without scraping.")
    parser.add_argument("--skip-telegram", action="store_true", help="Generate charts without sending them.")
    parser.add_argument("--max-pairs", type=int, default=None, help="Optional limit for testing.")
    args = parser.parse_args()

    settings = load_settings(args.config)
    return run_daily_job(
        settings,
        skip_telegram=args.skip_telegram,
        skip_refresh=args.skip_refresh,
        max_pairs=args.max_pairs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
