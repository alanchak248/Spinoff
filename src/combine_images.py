from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from src.universe import SpinoffRecord, days_since_spinoff

CELL_SIZE = (1216, 680)
MARGIN = 24
GUTTER = 20
HEADER_MIN_HEIGHT = 248
SECTION_HEADER_HEIGHT = 48


def combine_company_image(
    *,
    record: SpinoffRecord,
    company_role: str,
    chart_images: dict[str, Path],
    reference_date: date,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    title_font = _load_font(38)
    detail_font = _load_font(22)
    section_font = _load_font(24)

    is_child = company_role.lower() == "child"
    company_label = "Child Company" if is_child else "Parent Company"
    company_ticker = record.spunoff_ticker if is_child else record.parent_ticker
    company_name = record.spunoff_name if is_child else record.parent_name

    title_text = f"{company_ticker} | {company_name or 'Unknown company'} | {company_label}"
    parent_text = f"Parent: {record.parent_ticker} | {record.parent_name or 'Unknown company'}"
    child_text = f"Child: {record.spunoff_ticker} | {record.spunoff_name or 'Unknown company'}"
    detail_text = (
        f"Spin-off date: {record.spinoff_date.isoformat()}  |  "
        f"Days since spin-off: {days_since_spinoff(record, reference_date)}"
    )

    canvas_width = CELL_SIZE[0] + (MARGIN * 2)
    measurement_draw = ImageDraw.Draw(Image.new("RGB", (1, 1), "#ffffff"))
    max_text_width = canvas_width - (MARGIN * 2)

    title_lines = _wrap_text(measurement_draw, title_text, title_font, max_text_width)
    parent_lines = _wrap_text(measurement_draw, parent_text, detail_font, max_text_width)
    child_lines = _wrap_text(measurement_draw, child_text, detail_font, max_text_width)
    detail_lines = _wrap_text(measurement_draw, detail_text, detail_font, max_text_width)

    header_height = _measure_header_height(
        measurement_draw,
        title_lines=title_lines,
        parent_lines=parent_lines,
        child_lines=child_lines,
        detail_lines=detail_lines,
        title_font=title_font,
        detail_font=detail_font,
    )

    canvas_height = (
        header_height
        + (SECTION_HEADER_HEIGHT * 2)
        + (CELL_SIZE[1] * 2)
        + GUTTER
        + (MARGIN * 2)
    )

    canvas = Image.new("RGB", (canvas_width, canvas_height), "#f5f7fb")
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, canvas_width, header_height), fill="#0f172a")
    current_y = 28
    current_y = _draw_wrapped_text(draw, title_lines, (MARGIN, current_y), title_font, "#ffffff", 10)
    current_y += 10
    current_y = _draw_wrapped_text(draw, parent_lines, (MARGIN, current_y), detail_font, "#e2e8f0", 8)
    current_y = _draw_wrapped_text(draw, child_lines, (MARGIN, current_y), detail_font, "#e2e8f0", 8)
    _draw_wrapped_text(draw, detail_lines, (MARGIN, current_y + 6), detail_font, "#94a3b8", 8)

    weekly_header_y = header_height + MARGIN
    _draw_section_header(draw, weekly_header_y, section_font, "Weekly Chart")
    weekly_image = _load_chart_tile(chart_images["1wk"])
    canvas.paste(weekly_image, (MARGIN, weekly_header_y + SECTION_HEADER_HEIGHT))

    daily_header_y = weekly_header_y + SECTION_HEADER_HEIGHT + CELL_SIZE[1] + GUTTER
    _draw_section_header(draw, daily_header_y, section_font, "Daily Chart")
    daily_image = _load_chart_tile(chart_images["1d"])
    canvas.paste(daily_image, (MARGIN, daily_header_y + SECTION_HEADER_HEIGHT))

    canvas.save(output_path, format="JPEG", quality=92, optimize=True)
    return output_path


def _draw_section_header(
    draw: ImageDraw.ImageDraw,
    y: int,
    font: ImageFont.ImageFont,
    text: str,
) -> None:
    draw.rounded_rectangle(
        (MARGIN, y, MARGIN + CELL_SIZE[0], y + SECTION_HEADER_HEIGHT),
        radius=12,
        fill="#e2e8f0",
    )
    draw.text((MARGIN + 18, y + 11), text, fill="#0f172a", font=font)


def _measure_header_height(
    draw: ImageDraw.ImageDraw,
    *,
    title_lines: list[str],
    parent_lines: list[str],
    child_lines: list[str],
    detail_lines: list[str],
    title_font: ImageFont.ImageFont,
    detail_font: ImageFont.ImageFont,
) -> int:
    current_y = 28
    current_y = _measure_wrapped_text_height(draw, title_lines, current_y, title_font, 10)
    current_y += 10
    current_y = _measure_wrapped_text_height(draw, parent_lines, current_y, detail_font, 8)
    current_y = _measure_wrapped_text_height(draw, child_lines, current_y, detail_font, 8)
    current_y = _measure_wrapped_text_height(draw, detail_lines, current_y + 6, detail_font, 8)
    current_y += 24
    return max(HEADER_MIN_HEIGHT, current_y)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    origin: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    line_spacing: int,
) -> int:
    x, y = origin
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        bbox = draw.textbbox((x, y), line, font=font)
        y = bbox[3] + line_spacing
    return y


def _measure_wrapped_text_height(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    start_y: int,
    font: ImageFont.ImageFont,
    line_spacing: int,
) -> int:
    y = start_y
    for line in lines:
        bbox = draw.textbbox((0, y), line, font=font)
        y = bbox[3] + line_spacing
    return y


def _load_chart_tile(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    resized = image.resize(CELL_SIZE, Image.Resampling.LANCZOS)
    return ImageOps.expand(resized, border=1, fill="#cbd5e1")


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
