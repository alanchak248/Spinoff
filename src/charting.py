from __future__ import annotations

from pathlib import Path
from datetime import date

import mplfinance as mpf
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

CHART_PIXEL_SIZE = (1200, 760)
MIN_BARS_BY_TIMEFRAME = {
    "1wk": 2,
    "1d": 5,
}
MAX_STALENESS_DAYS = {
    "1wk": 21,
    "1d": 10,
}


def has_usable_chart_data(
    data: pd.DataFrame,
    *,
    timeframe: str,
    reference_date: date | None = None,
) -> bool:
    minimum_bars = MIN_BARS_BY_TIMEFRAME.get(timeframe, 2)
    if data.empty or len(data.index) < minimum_bars:
        return False
    return _stale_message(data, timeframe=timeframe, reference_date=reference_date) is None


def render_candlestick_chart(
    data: pd.DataFrame,
    *,
    ticker: str,
    timeframe: str,
    output_path: Path,
    reference_date: date | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    minimum_bars = MIN_BARS_BY_TIMEFRAME.get(timeframe, 2)
    if data.empty or len(data.index) < minimum_bars:
        available_bars = len(data.index) if not data.empty else 0
        _render_placeholder(
            output_path,
            title=f"{ticker} | {timeframe}",
            message=_placeholder_message(timeframe, available_bars, minimum_bars),
        )
        return output_path

    stale_message = _stale_message(data, timeframe=timeframe, reference_date=reference_date)
    if stale_message:
        _render_placeholder(
            output_path,
            title=f"{ticker} | {timeframe}",
            message=stale_message,
        )
        return output_path

    plot_data = data.copy()
    plot_data.index = pd.DatetimeIndex(plot_data.index)

    market_colors = mpf.make_marketcolors(
        up="#1f7a3f",
        down="#c0392b",
        edge="inherit",
        wick="inherit",
        volume="inherit",
    )
    style = mpf.make_mpf_style(
        base_mpf_style="yahoo",
        marketcolors=market_colors,
        gridstyle="-",
        gridcolor="#d9dde3",
        facecolor="#ffffff",
        figcolor="#ffffff",
    )

    mpf.plot(
        plot_data,
        type="candle",
        style=style,
        title=f"{ticker} | {timeframe}",
        ylabel="Price",
        volume=False,
        tight_layout=True,
        xrotation=0,
        figratio=(10, 6),
        figscale=1.0,
        datetime_format=_datetime_format_for_timeframe(timeframe),
        savefig={
            "fname": str(output_path),
            "dpi": 140,
            "bbox_inches": "tight",
            "pad_inches": 0.20,
        },
    )
    return output_path


def _render_placeholder(output_path: Path, *, title: str, message: str) -> None:
    image = Image.new("RGB", CHART_PIXEL_SIZE, "#ffffff")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(28)
    status_font = _load_font(34)
    body_font = _load_font(24)

    draw.rectangle((0, 0, CHART_PIXEL_SIZE[0], 72), fill="#0f172a")
    draw.text((24, 22), title, fill="#ffffff", font=title_font)

    card_margin_x = 110
    card_top = 170
    card_bottom = CHART_PIXEL_SIZE[1] - 110
    draw.rounded_rectangle(
        (card_margin_x, card_top, CHART_PIXEL_SIZE[0] - card_margin_x, card_bottom),
        radius=24,
        fill="#f8fafc",
        outline="#cbd5e1",
        width=3,
    )

    status_text = _placeholder_status(message)
    status_bbox = draw.textbbox((0, 0), status_text, font=status_font)
    status_width = status_bbox[2] - status_bbox[0]
    status_x = (CHART_PIXEL_SIZE[0] - status_width) / 2
    status_y = card_top + 52
    draw.text((status_x, status_y), status_text, fill="#0f172a", font=status_font)

    wrapped_lines = _wrap_lines(draw, message, body_font, CHART_PIXEL_SIZE[0] - (card_margin_x * 2) - 80)
    body_text = "\n".join(wrapped_lines)
    body_bbox = draw.multiline_textbbox((0, 0), body_text, font=body_font, spacing=10, align="center")
    body_width = body_bbox[2] - body_bbox[0]
    body_height = body_bbox[3] - body_bbox[1]
    body_x = (CHART_PIXEL_SIZE[0] - body_width) / 2
    body_y = status_y + 92
    if body_y + body_height > card_bottom - 40:
        body_y = card_bottom - body_height - 40
    draw.multiline_text(
        (body_x, body_y),
        body_text,
        fill="#334155",
        font=body_font,
        spacing=10,
        align="center",
    )
    image.save(output_path)


def _placeholder_message(timeframe: str, available_bars: int, minimum_bars: int) -> str:
    if available_bars == 0:
        return f"No usable {timeframe} data returned."
    return (
        f"Only {available_bars} {timeframe} bars available.\n"
        f"Need at least {minimum_bars} bars for a readable chart."
    )


def _stale_message(
    data: pd.DataFrame,
    *,
    timeframe: str,
    reference_date: date | None,
) -> str | None:
    if reference_date is None or data.empty:
        return None

    last_bar_date = pd.Timestamp(data.index.max()).date()
    max_age_days = MAX_STALENESS_DAYS.get(timeframe)
    if max_age_days is None:
        return None

    age_days = (reference_date - last_bar_date).days
    if age_days <= max_age_days:
        return None

    return (
        f"Latest {timeframe} bar is stale.\n"
        f"Latest bar date: {last_bar_date.isoformat()}.\n"
        f"Data age: {age_days} days."
    )


def _datetime_format_for_timeframe(timeframe: str) -> str:
    return "%Y-%m"


def _placeholder_status(message: str) -> str:
    lowered = message.lower()
    if "stale" in lowered:
        return "Stale Data"
    if "only" in lowered or "need at least" in lowered:
        return "Insufficient History"
    return "No Market Data"


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        words = raw_line.split()
        if not words:
            lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
