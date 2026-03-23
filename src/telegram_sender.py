from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable

import requests

from src.settings import TelegramSettings

LOGGER = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self, settings: TelegramSettings) -> None:
        self.settings = settings
        if not settings.bot_token:
            raise ValueError("Telegram bot token is missing")
        if not settings.chat_ids:
            raise ValueError("Telegram chat ID is missing")
        self.base_url = f"https://api.telegram.org/bot{settings.bot_token}"

    def send_images(self, image_paths: Iterable[Path]) -> None:
        for chat_id in self.settings.chat_ids:
            for image_path in image_paths:
                try:
                    self._send_photo(chat_id, image_path, "")
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error(
                        "Telegram send failed for %s to chat %s: %s",
                        image_path.name,
                        chat_id,
                        exc,
                        exc_info=True,
                    )

    def send_text(self, text: str) -> None:
        for chat_id in self.settings.chat_ids:
            try:
                response = requests.post(
                    f"{self.base_url}/sendMessage",
                    data={
                        "chat_id": chat_id,
                        "text": text,
                    },
                    timeout=self.settings.timeout_seconds,
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                LOGGER.error(
                    "Telegram text send failed for chat %s: %s",
                    chat_id,
                    exc,
                    exc_info=True,
                )

    def send_image_groups(self, image_groups: Iterable[list[Path]]) -> None:
        for chat_id in self.settings.chat_ids:
            for image_group in image_groups:
                if not image_group:
                    continue
                for image_path in image_group:
                    try:
                        self._send_photo(chat_id, image_path, "")
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.error(
                            "Telegram send failed for %s to chat %s: %s",
                            image_path.name,
                            chat_id,
                            exc,
                            exc_info=True,
                        )

    def _send_photo(self, chat_id: str, image_path: Path, caption: str) -> None:
        with image_path.open("rb") as photo:
            response = requests.post(
                f"{self.base_url}/sendPhoto",
                data={
                    "chat_id": chat_id,
                    "caption": caption,
                },
                files={"photo": (image_path.name, photo, "image/jpeg")},
                timeout=self.settings.timeout_seconds,
            )
        response.raise_for_status()
