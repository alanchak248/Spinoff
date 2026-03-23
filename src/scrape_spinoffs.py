from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.settings import Settings, load_settings
from src.universe import SpinoffRecord, UniverseStore, dedupe_records, normalize_ticker

LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


def build_source_urls(base_url: str, reference_date: date, lookback_months: int) -> list[str]:
    cutoff_date = (pd.Timestamp(reference_date) - pd.DateOffset(months=lookback_months)).date()
    cutoff_year = cutoff_date.year
    urls = [f"{base_url}/"]
    for year in range(reference_date.year, cutoff_year - 1, -1):
        urls.append(f"{base_url}/{year}/")
    return urls


def scrape_recent_spinoffs(
    settings: Settings,
    *,
    reference_date: date | None = None,
    session: requests.Session | None = None,
) -> tuple[list[SpinoffRecord], list[str]]:
    today = reference_date or date.today()
    cutoff_date = (pd.Timestamp(today) - pd.DateOffset(months=settings.stockanalysis.lookback_months)).date()
    source_urls = build_source_urls(
        settings.stockanalysis.base_url,
        reference_date=today,
        lookback_months=settings.stockanalysis.lookback_months,
    )

    close_session = False
    if session is None:
        session = requests.Session()
        close_session = True

    session.headers.update({"User-Agent": USER_AGENT})

    records: list[SpinoffRecord] = []
    try:
        for url in source_urls:
            try:
                records.extend(
                    _scrape_page(
                        session=session,
                        url=url,
                        cutoff_date=cutoff_date,
                        timeout_seconds=settings.stockanalysis.request_timeout_seconds,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.error("Failed to scrape %s: %s", url, exc, exc_info=True)
    finally:
        if close_session:
            session.close()

    return dedupe_records(records), source_urls


def save_scraped_universe(
    settings: Settings,
    records: Iterable[SpinoffRecord],
    source_urls: list[str],
) -> None:
    UniverseStore(settings.universe.path).save(
        list(records),
        fetched_at=datetime.utcnow(),
        source_urls=source_urls,
    )


def _scrape_page(
    *,
    session: requests.Session,
    url: str,
    cutoff_date: date,
    timeout_seconds: int,
) -> list[SpinoffRecord]:
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    if not tables:
        LOGGER.warning("No tables found on %s", url)
        return []

    table = tables[0]
    table.columns = [str(column).strip() for column in table.columns]

    required_columns = {"Date", "Parent", "New Stock", "Parent Company", "New Company"}
    missing_columns = required_columns.difference(table.columns)
    if missing_columns:
        raise ValueError(f"Missing expected columns on {url}: {sorted(missing_columns)}")

    records: list[SpinoffRecord] = []
    for raw_row in table.to_dict(orient="records"):
        record = _parse_row(raw_row, source_url=url)
        if not record:
            continue
        if record.spinoff_date < cutoff_date:
            continue
        records.append(record)

    LOGGER.info("Scraped %s qualifying records from %s", len(records), url)
    return records


def _parse_row(raw_row: dict[str, object], *, source_url: str) -> SpinoffRecord | None:
    parent_ticker = normalize_ticker(raw_row.get("Parent"))
    spunoff_ticker = normalize_ticker(raw_row.get("New Stock"))
    if not parent_ticker or not spunoff_ticker:
        return None

    parsed_date = pd.to_datetime(str(raw_row.get("Date")), errors="coerce")
    if pd.isna(parsed_date):
        return None

    return SpinoffRecord(
        parent_ticker=parent_ticker,
        spunoff_ticker=spunoff_ticker,
        parent_name=_clean_text(raw_row.get("Parent Company")),
        spunoff_name=_clean_text(raw_row.get("New Company")),
        spinoff_date=parsed_date.date(),
        source_url=source_url,
    )


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() == "nan":
        return None
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape recent stock spin-offs and persist them locally.")
    parser.add_argument("--config", help="Optional path to a settings YAML file.", default=None)
    args = parser.parse_args()

    settings = load_settings(args.config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    records, source_urls = scrape_recent_spinoffs(settings)
    save_scraped_universe(settings, records, source_urls)
    LOGGER.info("Saved %s records to %s", len(records), settings.universe.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
