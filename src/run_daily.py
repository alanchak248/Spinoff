from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.charting import has_usable_chart_data, render_candlestick_chart
from src.combine_images import combine_company_image
from src.fetch_prices import PriceBundle, fetch_price_bundle
from src.logging_utils import configure_logging
from src.scrape_spinoffs import scrape_recent_spinoffs
from src.settings import Settings, load_settings
from src.telegram_sender import TelegramSender
from src.universe import SpinoffRecord, UniverseStore, sort_records

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and send daily spin-off company chart pairs.")
    parser.add_argument("--config", help="Optional path to a settings YAML file.", default=None)
    parser.add_argument("--skip-telegram", action="store_true", help="Generate images without sending them.")
    parser.add_argument("--skip-refresh", action="store_true", help="Use the stored universe without scraping.")
    parser.add_argument("--max-pairs", type=int, default=None, help="Limit the number of processed pairs for a run.")
    args = parser.parse_args()

    settings = load_settings(args.config)
    return run_daily_job(
        settings,
        skip_telegram=args.skip_telegram,
        skip_refresh=args.skip_refresh,
        max_pairs=args.max_pairs,
    )


def run_daily_job(
    settings: Settings,
    *,
    skip_telegram: bool = False,
    skip_refresh: bool = False,
    max_pairs: int | None = None,
) -> int:
    log_path = configure_logging(settings.log_dir)
    LOGGER.info("Logging to %s", log_path)

    reference_date = date.today()
    records = _load_or_refresh_universe(settings, reference_date=reference_date, skip_refresh=skip_refresh)
    if not records:
        LOGGER.error("No spin-off records are available to process.")
        return 1

    if not settings.market_data.is_configured:
        LOGGER.error(
            "Alpaca credentials are missing. Set %s and %s before running the daily job.",
            settings.market_data.api_key_env,
            settings.market_data.api_secret_env,
        )
        return 1

    limit = max_pairs if max_pairs is not None else settings.runtime.max_pairs_per_run
    if limit is not None:
        records = records[:limit]

    if settings.charts.cleanup_before_run:
        _reset_chart_output(settings.charts.output_dir)

    run_output_dir = settings.charts.output_dir / reference_date.isoformat()
    part_output_dir = run_output_dir / settings.charts.part_dir_name
    run_output_dir.mkdir(parents=True, exist_ok=True)
    part_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        final_image_groups: list[list[Path]] = []
        for record in records:
            try:
                image_group = process_spinoff_pair(
                    record,
                    settings=settings,
                    reference_date=reference_date,
                    run_output_dir=run_output_dir,
                    part_output_dir=part_output_dir,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.error(
                    "Failed to process %s/%s: %s",
                    record.spunoff_ticker,
                    record.parent_ticker,
                    exc,
                    exc_info=True,
                )
                continue
            if image_group:
                final_image_groups.append(image_group)

        total_images = sum(len(image_group) for image_group in final_image_groups)
        LOGGER.info("Generated %s deliverable groups (%s total images)", len(final_image_groups), total_images)
        if not final_image_groups:
            LOGGER.error("No deliverable company images were generated.")
            return 1

        if not skip_telegram:
            if settings.telegram.is_configured:
                TelegramSender(settings.telegram).send_image_groups(final_image_groups)
            else:
                LOGGER.warning(
                    "Telegram is enabled but credentials are missing. Set %s and %s to send images.",
                    settings.telegram.bot_token_env,
                    settings.telegram.chat_id_env,
                )

        return 0
    finally:
        if settings.charts.cleanup_after_run and not skip_telegram:
            _remove_chart_output(settings.charts.output_dir)


def process_spinoff_pair(
    record: SpinoffRecord,
    *,
    settings: Settings,
    reference_date: date,
    run_output_dir: Path,
    part_output_dir: Path,
) -> list[Path]:
    LOGGER.info(
        "Processing pair %s/%s from %s",
        record.spunoff_ticker,
        record.parent_ticker,
        record.spinoff_date,
    )

    spunoff_bundle = fetch_price_bundle(record.spunoff_ticker, settings.market_data)
    parent_bundle = fetch_price_bundle(record.parent_ticker, settings.market_data)
    spunoff_bundle = _clip_bundle_start(spunoff_bundle, record.spinoff_date)

    pair_slug = _pair_slug(record)
    pair_part_dir = part_output_dir / pair_slug

    deliverable_images: list[Path] = []

    if _bundle_has_usable_chart(spunoff_bundle, reference_date=reference_date):
        spunoff_images = _render_company_bundle(
            bundle=spunoff_bundle,
            ticker=record.spunoff_ticker,
            output_dir=pair_part_dir / "spunoff",
            reference_date=reference_date,
        )
        child_output_path = run_output_dir / f"{pair_slug}_child.jpg"
        deliverable_images.append(
            combine_company_image(
                record=record,
                company_role="child",
                chart_images=spunoff_images,
                reference_date=reference_date,
                output_path=child_output_path,
            )
        )
    else:
        LOGGER.info("Skipping child image for %s because weekly/daily data is not usable.", record.spunoff_ticker)

    if _bundle_has_usable_chart(parent_bundle, reference_date=reference_date):
        parent_images = _render_company_bundle(
            bundle=parent_bundle,
            ticker=record.parent_ticker,
            output_dir=pair_part_dir / "parent",
            reference_date=reference_date,
        )
        parent_output_path = run_output_dir / f"{pair_slug}_parent.jpg"
        deliverable_images.append(
            combine_company_image(
                record=record,
                company_role="parent",
                chart_images=parent_images,
                reference_date=reference_date,
                output_path=parent_output_path,
            )
        )
    else:
        LOGGER.info("Skipping parent image for %s because weekly/daily data is not usable.", record.parent_ticker)

    return deliverable_images


def _load_or_refresh_universe(
    settings: Settings,
    *,
    reference_date: date,
    skip_refresh: bool,
) -> list[SpinoffRecord]:
    store = UniverseStore(settings.universe.path)
    stored_records = store.load()

    should_refresh = settings.universe.refresh_on_run and not skip_refresh
    if not should_refresh:
        return sort_records(stored_records)

    try:
        scraped_records, source_urls = scrape_recent_spinoffs(settings, reference_date=reference_date)
        if scraped_records:
            store.save(scraped_records, fetched_at=datetime.utcnow(), source_urls=source_urls)
            return sort_records(scraped_records)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Universe refresh failed, falling back to stored data: %s", exc, exc_info=True)

    return sort_records(stored_records)


def _render_company_bundle(
    *,
    bundle: PriceBundle,
    ticker: str,
    output_dir: Path,
    reference_date: date,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timeframe_map = {
        "1wk": bundle.weekly,
        "1d": bundle.daily,
    }

    rendered_paths: dict[str, Path] = {}
    for timeframe, data in timeframe_map.items():
        chart_path = output_dir / f"{ticker}_{timeframe}.png"
        render_candlestick_chart(
            data,
            ticker=ticker,
            timeframe=timeframe,
            output_path=chart_path,
            reference_date=reference_date,
        )
        rendered_paths[timeframe] = chart_path
    return rendered_paths


def _pair_slug(record: SpinoffRecord) -> str:
    return f"{record.spinoff_date.isoformat()}_{record.spunoff_ticker}_{record.parent_ticker}"


def _bundle_has_usable_chart(bundle: PriceBundle, *, reference_date: date) -> bool:
    timeframe_map = {
        "1wk": bundle.weekly,
        "1d": bundle.daily,
    }
    return any(
        has_usable_chart_data(data, timeframe=timeframe, reference_date=reference_date)
        for timeframe, data in timeframe_map.items()
    )


def _reset_chart_output(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _remove_chart_output(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)


def _clip_bundle_start(bundle: PriceBundle, start_date: date) -> PriceBundle:
    start_timestamp = datetime.combine(start_date, datetime.min.time())
    return PriceBundle(
        ticker=bundle.ticker,
        source_symbol=bundle.source_symbol,
        daily=_clip_frame_start(bundle.daily, start_timestamp),
        weekly=_clip_frame_start(bundle.weekly, start_timestamp),
    )


def _clip_frame_start(frame: object, start_timestamp: datetime):
    if not isinstance(frame, pd.DataFrame):
        return frame
    if frame.empty:
        return frame
    clipped = frame.loc[frame.index >= start_timestamp]
    return _drop_flat_zero_volume_edges(clipped)


def _drop_flat_zero_volume_edges(frame: pd.DataFrame) -> pd.DataFrame:
    trimmed = frame.copy()
    while not trimmed.empty and _is_flat_zero_volume_bar(trimmed.iloc[0]):
        trimmed = trimmed.iloc[1:]
    while not trimmed.empty and _is_flat_zero_volume_bar(trimmed.iloc[-1]):
        trimmed = trimmed.iloc[:-1]
    return trimmed


def _is_flat_zero_volume_bar(row: pd.Series) -> bool:
    is_flat_bar = (
        pd.notna(row["Open"])
        and row["Open"] == row["High"] == row["Low"] == row["Close"]
    )
    is_zero_volume = pd.isna(row["Volume"]) or float(row["Volume"]) == 0.0
    return bool(is_flat_bar and is_zero_volume)


if __name__ == "__main__":
    raise SystemExit(main())
