from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import requests

from src.settings import MarketDataSettings

LOGGER = logging.getLogger(__name__)
OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
MAX_LIMIT = 10_000


@dataclass(frozen=True)
class PriceBundle:
    ticker: str
    source_symbol: str
    daily: pd.DataFrame
    weekly: pd.DataFrame


class AlpacaMarketDataClient:
    def __init__(self, settings: MarketDataSettings) -> None:
        if not settings.is_configured:
            raise ValueError(
                "Alpaca credentials are missing. Set "
                f"{settings.api_key_env} and {settings.api_secret_env}."
            )
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": settings.api_key or "",
                "APCA-API-SECRET-KEY": settings.api_secret or "",
                "Accept": "application/json",
            }
        )

    def get_stock_bars(
        self,
        symbol: str,
        *,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> pd.DataFrame:
        url = f"{self.settings.data_base_url}/stocks/{symbol}/bars"
        params: dict[str, Any] = {
            "timeframe": timeframe,
            "start": _format_timestamp(start),
            "end": _format_timestamp(end),
            "limit": min(limit, MAX_LIMIT),
            "feed": self.settings.feed,
            "adjustment": self.settings.adjustment,
            "sort": "desc",
        }

        all_bars: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            if page_token:
                params["page_token"] = page_token
            else:
                params.pop("page_token", None)

            response = self.session.get(
                url,
                params=params,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            bars = payload.get("bars", [])
            if isinstance(bars, list):
                all_bars.extend(bars)

            page_token = payload.get("next_page_token")
            if not page_token or len(all_bars) >= limit:
                break

        if len(all_bars) > limit:
            all_bars = all_bars[-limit:]

        return _bars_to_frame(all_bars)


def fetch_price_bundle(ticker: str, settings: MarketDataSettings) -> PriceBundle:
    client = AlpacaMarketDataClient(settings)
    symbol = ticker.upper()
    now_utc = datetime.now(UTC)
    daily_start = now_utc - timedelta(days=365 * settings.daily_lookback_years)

    daily = client.get_stock_bars(
        symbol,
        timeframe="1Day",
        start=daily_start,
        end=now_utc,
        limit=settings.chart_bars.daily,
    )
    weekly = client.get_stock_bars(
        symbol,
        timeframe="1Week",
        start=daily_start,
        end=now_utc,
        limit=settings.chart_bars.weekly,
    )

    if daily.empty and weekly.empty:
        raise ValueError(f"No Alpaca bars returned for {symbol}")

    return PriceBundle(
        ticker=ticker,
        source_symbol=symbol,
        daily=daily,
        weekly=weekly,
    )


def _bars_to_frame(bars: list[dict[str, Any]]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    frame = pd.DataFrame(bars)
    rename_map = {
        "o": "Open",
        "h": "High",
        "l": "Low",
        "c": "Close",
        "v": "Volume",
        "t": "Timestamp",
    }
    frame = frame.rename(columns=rename_map)
    if "Timestamp" not in frame.columns:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    for column in OHLCV_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0 if column == "Volume" else pd.NA

    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["Timestamp"])
    frame = frame.set_index("Timestamp")
    frame = frame[OHLCV_COLUMNS]
    frame = frame.dropna(subset=["Open", "High", "Low", "Close"], how="all")
    if frame.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    if frame.index.tz is not None:
        frame.index = frame.index.tz_convert("America/New_York").tz_localize(None)

    frame.index = pd.DatetimeIndex(frame.index)
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return _drop_flat_zero_volume_tail(frame)


def _drop_flat_zero_volume_tail(frame: pd.DataFrame) -> pd.DataFrame:
    trimmed = frame.copy()
    while not trimmed.empty:
        last_row = trimmed.iloc[-1]
        is_flat_bar = (
            pd.notna(last_row["Open"])
            and last_row["Open"] == last_row["High"] == last_row["Low"] == last_row["Close"]
        )
        is_zero_volume = pd.isna(last_row["Volume"]) or float(last_row["Volume"]) == 0.0
        if not (is_flat_bar and is_zero_volume):
            break
        trimmed = trimmed.iloc[:-1]
    return trimmed


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
