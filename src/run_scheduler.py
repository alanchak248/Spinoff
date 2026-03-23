from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.logging_utils import configure_logging
from src.run_daily import run_daily_job
from src.settings import load_settings

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the spin-off tracker every day at the configured time.")
    parser.add_argument("--config", help="Optional path to a settings YAML file.", default=None)
    parser.add_argument("--skip-telegram", action="store_true", help="Generate images without sending them.")
    parser.add_argument("--skip-refresh", action="store_true", help="Use the stored universe without scraping.")
    parser.add_argument("--max-pairs", type=int, default=None, help="Limit the number of processed pairs for each run.")
    args = parser.parse_args()

    settings = load_settings(args.config)
    timezone = ZoneInfo(settings.schedule.timezone)
    log_path = configure_logging(settings.log_dir, "run_scheduler")
    LOGGER.info("Scheduler logging to %s", log_path)

    while True:
        next_run = _next_run_time(
            timezone=timezone,
            hour=settings.schedule.hour,
            minute=settings.schedule.minute,
        )
        LOGGER.info("Next scheduled run at %s", next_run.isoformat())

        while True:
            now = datetime.now(timezone)
            seconds_until_run = (next_run - now).total_seconds()
            if seconds_until_run <= 0:
                break
            time.sleep(min(seconds_until_run, 60))

        run_daily_job(
            settings,
            skip_telegram=args.skip_telegram,
            skip_refresh=args.skip_refresh,
            max_pairs=args.max_pairs,
        )


def _next_run_time(*, timezone: ZoneInfo, hour: int, minute: int) -> datetime:
    now = datetime.now(timezone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


if __name__ == "__main__":
    raise SystemExit(main())
