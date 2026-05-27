from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger("audit")


class AuditAction(StrEnum):
    BOT_START = "bot_start"
    INSTALL_PROTOCOL = "install_protocol"
    CREATE_CLIENT = "create_client"
    DELETE_CLIENT = "delete_client"
    GET_LINK = "get_link"
    BACKUP = "backup"
    UPDATE = "update"
    ADMIN_DENIED = "admin_denied"
    RATE_LIMIT_HIT = "rate_limit_hit"


class AuditLogger:
    def log(
        self,
        actor_id: int,
        action: AuditAction,
        target_type: str,
        target_id: str,
        status: str,
        details: str = "",
    ) -> None:
        logger.info(
            "audit_event",
            extra={
                "actor_id": actor_id,
                "action": action.value,
                "target_type": target_type,
                "target_id": target_id,
                "status": status,
                "details": details,
            },
        )
