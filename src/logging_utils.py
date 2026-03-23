from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def configure_logging(log_dir: Path, run_name: str = "run_daily") -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{run_name}_{datetime.now().strftime('%Y%m%d')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    for noisy_logger in ("matplotlib", "PIL", "urllib3", "yfinance"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return log_path
