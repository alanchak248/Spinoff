from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger(__name__)
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,14}$")


@dataclass(frozen=True)
class SpinoffRecord:
    parent_ticker: str
    spunoff_ticker: str
    parent_name: str | None
    spunoff_name: str | None
    spinoff_date: date
    source_url: str

    @property
    def key(self) -> str:
        return f"{self.spinoff_date.isoformat()}::{self.parent_ticker}::{self.spunoff_ticker}"

    def to_dict(self) -> dict[str, object]:
        return {
            "parent_ticker": self.parent_ticker,
            "spunoff_ticker": self.spunoff_ticker,
            "parent_name": self.parent_name,
            "spunoff_name": self.spunoff_name,
            "spinoff_date": self.spinoff_date.isoformat(),
            "source_url": self.source_url,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "SpinoffRecord":
        return cls(
            parent_ticker=str(payload["parent_ticker"]),
            spunoff_ticker=str(payload["spunoff_ticker"]),
            parent_name=_clean_optional_text(payload.get("parent_name")),
            spunoff_name=_clean_optional_text(payload.get("spunoff_name")),
            spinoff_date=date.fromisoformat(str(payload["spinoff_date"])),
            source_url=str(payload["source_url"]),
        )


class UniverseStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[SpinoffRecord]:
        if not self.path.exists():
            LOGGER.info("Universe file does not exist yet: %s", self.path)
            return []

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            LOGGER.error("Universe file is invalid JSON: %s", exc)
            return []

        raw_records = payload.get("records", []) if isinstance(payload, dict) else []
        records: list[SpinoffRecord] = []
        for raw_record in raw_records:
            if not isinstance(raw_record, dict):
                continue
            try:
                records.append(SpinoffRecord.from_dict(raw_record))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Skipping malformed universe record: %s", exc)
        return sort_records(records)

    def save(
        self,
        records: Iterable[SpinoffRecord],
        *,
        fetched_at: datetime | None = None,
        source_urls: list[str] | None = None,
    ) -> None:
        sorted_records = sort_records(records)
        payload = {
            "last_updated_at": (fetched_at or datetime.utcnow()).isoformat(),
            "record_count": len(sorted_records),
            "source_urls": source_urls or [],
            "records": [record.to_dict() for record in sorted_records],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_ticker(value: object) -> str | None:
    if value is None:
        return None
    ticker = str(value).strip().upper()
    if not ticker or ticker == "NAN":
        return None
    ticker = ticker.replace("/", "-")
    if not TICKER_PATTERN.match(ticker):
        return None
    return ticker


def dedupe_records(records: Iterable[SpinoffRecord]) -> list[SpinoffRecord]:
    deduped: dict[str, SpinoffRecord] = {}
    for record in records:
        existing = deduped.get(record.key)
        if existing is None:
            deduped[record.key] = record
            continue

        deduped[record.key] = record if _field_score(record) >= _field_score(existing) else existing

    return sort_records(deduped.values())


def sort_records(records: Iterable[SpinoffRecord]) -> list[SpinoffRecord]:
    return sorted(
        records,
        key=lambda record: (record.spinoff_date, record.spunoff_ticker, record.parent_ticker),
        reverse=True,
    )


def days_since_spinoff(record: SpinoffRecord, reference_date: date) -> int:
    return max(0, (reference_date - record.spinoff_date).days)


def _field_score(record: SpinoffRecord) -> int:
    return sum(
        1
        for value in (record.parent_name, record.spunoff_name, record.source_url)
        if value
    )


def _clean_optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() == "nan":
        return None
    return cleaned
