from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    level: AlertLevel
    title: str
    message: str
    source: str


AlertHandler = Callable[[Alert], Awaitable[None]]


class AlertDispatcher:
    def __init__(self) -> None:
        self._handlers: list[AlertHandler] = []

    def register_handler(self, handler: AlertHandler) -> None:
        self._handlers.append(handler)

    async def send(self, alert: Alert) -> None:
        logger.log(
            logging.WARNING if alert.level != AlertLevel.INFO else logging.INFO,
            "alert: %s - %s",
            alert.title,
            alert.message,
            extra={
                "alert_level": alert.level.value,
                "alert_source": alert.source,
            },
        )
        for handler in self._handlers:
            try:
                await handler(alert)
            except Exception:
                logger.exception("Alert handler failed")


class TelegramAlertHandler:
    def __init__(self, bot, admin_chat_ids: list[int]) -> None:
        self.bot = bot
        self.admin_chat_ids = admin_chat_ids

    async def __call__(self, alert: Alert) -> None:
        text = (
            f"[{alert.level.value.upper()}] {alert.title}\n"
            f"{alert.message}\n"
            f"Source: {alert.source}"
        )
        for chat_id in self.admin_chat_ids:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                logger.exception(
                    "Failed to send alert",
                    extra={"chat_id": chat_id},
                )
