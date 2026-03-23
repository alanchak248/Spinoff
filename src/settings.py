from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ChartBars:
    daily: int
    weekly: int


@dataclass(frozen=True)
class StockAnalysisSettings:
    base_url: str
    request_timeout_seconds: int
    lookback_months: int


@dataclass(frozen=True)
class UniverseSettings:
    path: Path
    refresh_on_run: bool


@dataclass(frozen=True)
class MarketDataSettings:
    data_base_url: str
    paper_trading_base_url: str
    daily_lookback_years: int
    request_timeout_seconds: int
    feed: str
    adjustment: str
    api_key_env: str
    api_secret_env: str
    api_key: str | None
    api_secret: str | None
    chart_bars: ChartBars

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)


@dataclass(frozen=True)
class ChartSettings:
    output_dir: Path
    part_dir_name: str
    cleanup_before_run: bool
    cleanup_after_run: bool


@dataclass(frozen=True)
class TelegramSettings:
    enabled: bool
    batch_size: int
    timeout_seconds: int
    bot_token_env: str
    chat_id_env: str
    bot_token: str | None
    chat_ids: tuple[str, ...]

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.bot_token and self.chat_ids)


@dataclass(frozen=True)
class RuntimeSettings:
    max_pairs_per_run: int | None


@dataclass(frozen=True)
class ScheduleSettings:
    timezone: str
    hour: int
    minute: int


@dataclass(frozen=True)
class Settings:
    project_root: Path
    stockanalysis: StockAnalysisSettings
    universe: UniverseSettings
    market_data: MarketDataSettings
    charts: ChartSettings
    telegram: TelegramSettings
    runtime: RuntimeSettings
    schedule: ScheduleSettings
    log_dir: Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_config_path() -> Path:
    root = project_root()
    preferred = root / "config" / "settings.yaml"
    if preferred.exists():
        return preferred
    return root / "config" / "settings.example.yaml"


def load_settings(config_path: str | Path | None = None) -> Settings:
    root = project_root()
    _load_dotenv(root / ".env")
    resolved_config_path = Path(config_path).resolve() if config_path else default_config_path()
    if not resolved_config_path.exists():
        raise FileNotFoundError(f"Settings file not found: {resolved_config_path}")

    raw_config = yaml.safe_load(resolved_config_path.read_text(encoding="utf-8")) or {}

    chart_bars = ChartBars(
        daily=int(_get_nested(raw_config, "market_data.chart_bars.1d", 252)),
        weekly=int(_get_nested(raw_config, "market_data.chart_bars.1wk", 104)),
    )

    stockanalysis = StockAnalysisSettings(
        base_url=str(
            _get_nested(
                raw_config,
                "stockanalysis.base_url",
                "https://stockanalysis.com/actions/spinoffs",
            )
        ).rstrip("/"),
        request_timeout_seconds=int(
            _get_nested(raw_config, "stockanalysis.request_timeout_seconds", 30)
        ),
        lookback_months=int(_get_nested(raw_config, "stockanalysis.lookback_months", 18)),
    )

    universe = UniverseSettings(
        path=_resolve_path(root, str(_get_nested(raw_config, "universe.path", "data/tracked_spinoffs.json"))),
        refresh_on_run=bool(_get_nested(raw_config, "universe.refresh_on_run", True)),
    )

    market_data = MarketDataSettings(
        data_base_url=str(
            _get_nested(raw_config, "market_data.data_base_url", "https://data.alpaca.markets/v2")
        ).rstrip("/"),
        paper_trading_base_url=str(
            _get_nested(raw_config, "market_data.paper_trading_base_url", "https://paper-api.alpaca.markets/v2")
        ).rstrip("/"),
        daily_lookback_years=int(
            _get_nested(raw_config, "market_data.daily_lookback_years", 10)
        ),
        request_timeout_seconds=int(
            _get_nested(raw_config, "market_data.request_timeout_seconds", 30)
        ),
        feed=str(_get_nested(raw_config, "market_data.feed", "iex")),
        adjustment=str(_get_nested(raw_config, "market_data.adjustment", "all")),
        api_key_env=str(_get_nested(raw_config, "market_data.api_key_env", "APCA_API_KEY_ID")),
        api_secret_env=str(_get_nested(raw_config, "market_data.api_secret_env", "APCA_API_SECRET_KEY")),
        api_key=(
            os.getenv(str(_get_nested(raw_config, "market_data.api_key_env", "APCA_API_KEY_ID")))
            or os.getenv("ALPACA_API_KEY_ID")
        ),
        api_secret=(
            os.getenv(str(_get_nested(raw_config, "market_data.api_secret_env", "APCA_API_SECRET_KEY")))
            or os.getenv("ALPACA_API_SECRET_KEY")
        ),
        chart_bars=chart_bars,
    )

    charts = ChartSettings(
        output_dir=_resolve_path(root, str(_get_nested(raw_config, "charts.output_dir", "output/charts"))),
        part_dir_name=str(_get_nested(raw_config, "charts.part_dir_name", "_parts")),
        cleanup_before_run=bool(_get_nested(raw_config, "charts.cleanup_before_run", True)),
        cleanup_after_run=bool(_get_nested(raw_config, "charts.cleanup_after_run", True)),
    )

    bot_token_env = str(_get_nested(raw_config, "telegram.bot_token_env", "TELEGRAM_BOT_TOKEN"))
    chat_id_env = str(_get_nested(raw_config, "telegram.chat_id_env", "TELEGRAM_CHAT_ID"))
    telegram = TelegramSettings(
        enabled=bool(_get_nested(raw_config, "telegram.enabled", True)),
        batch_size=max(1, min(10, int(_get_nested(raw_config, "telegram.batch_size", 10)))),
        timeout_seconds=int(_get_nested(raw_config, "telegram.timeout_seconds", 60)),
        bot_token_env=bot_token_env,
        chat_id_env=chat_id_env,
        bot_token=os.getenv(bot_token_env) or os.getenv("SPINOFF_TRACKER_TELEGRAM_BOT_TOKEN"),
        chat_ids=_parse_chat_ids(
            os.getenv(chat_id_env) or os.getenv("SPINOFF_TRACKER_TELEGRAM_CHAT_ID")
        ),
    )

    runtime = RuntimeSettings(
        max_pairs_per_run=_coerce_optional_int(_get_nested(raw_config, "runtime.max_pairs_per_run", None))
    )

    schedule = ScheduleSettings(
        timezone=str(_get_nested(raw_config, "schedule.timezone", "Asia/Hong_Kong")),
        hour=int(_get_nested(raw_config, "schedule.hour", 9)),
        minute=int(_get_nested(raw_config, "schedule.minute", 0)),
    )

    log_dir = _resolve_path(root, str(_get_nested(raw_config, "logging.output_dir", "output/logs")))

    return Settings(
        project_root=root,
        stockanalysis=stockanalysis,
        universe=universe,
        market_data=market_data,
        charts=charts,
        telegram=telegram,
        runtime=runtime,
        schedule=schedule,
        log_dir=log_dir,
    )


def _resolve_path(root: Path, raw_value: str) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return root / path


def _get_nested(config: dict[str, Any], path: str, default: Any) -> Any:
    value: Any = config
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def _coerce_optional_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    return int(value)


def _parse_chat_ids(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ()
    chat_ids = [item.strip() for item in raw_value.split(",")]
    return tuple(chat_id for chat_id in chat_ids if chat_id)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
