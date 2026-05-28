from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.repositories import AuditRepository

logger = logging.getLogger("audit")

_REDACT_KEYS = {"password", "secret", "token", "key", "uuid"}


def _redact_details(details: str) -> str:
    lowered = details.lower()
    for kw in _REDACT_KEYS:
        if kw in lowered:
            return "[REDACTED]"
    return details


class AuditAction(StrEnum):
    BOT_START = "bot_start"
    INSTALL_PROTOCOL = "install_protocol"
    CREATE_CLIENT = "create_client"
    DELETE_CLIENT = "delete_client"
    GET_LINK = "get_link"
    BACKUP = "backup"
    RESTORE = "restore"
    UPDATE = "update"
    HEALTH_CHECK = "health_check"
    CONFIG_CHANGE = "config_change"
    ADMIN_DENIED = "admin_denied"
    RATE_LIMIT_HIT = "rate_limit_hit"


class AuditLogger:
    def __init__(self, repository: AuditRepository | None = None) -> None:
        self._repository = repository

    def set_repository(self, repository: AuditRepository) -> None:
        self._repository = repository

    def log(
        self,
        actor_id: int,
        action: AuditAction,
        target_type: str,
        target_id: str,
        status: str,
        details: str = "",
    ) -> None:
        safe_details = _redact_details(details)
        logger.info(
            "audit_event",
            extra={
                "actor_id": actor_id,
                "action": action.value,
                "target_type": target_type,
                "target_id": target_id,
                "status": status,
                "details": safe_details,
            },
        )
        if self._repository is not None:
            try:
                import asyncio

                loop = asyncio.get_running_loop()
                loop.create_task(
                    self._repository.log(
                        actor_telegram_user_id=actor_id,
                        action=action.value,
                        target_type=target_type,
                        target_id=target_id,
                        status=status,
                        details_redacted=safe_details,
                    )
                )
            except RuntimeError:
                pass
