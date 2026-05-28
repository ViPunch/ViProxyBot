from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.enums import ProtocolType
from src.infrastructure.alerting import Alert, AlertDispatcher, AlertLevel
from src.services.protocol_registry import ProtocolRegistry

if TYPE_CHECKING:
    import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    bot_alive: bool
    db_healthy: bool
    protocols: dict[ProtocolType, bool]
    overall_healthy: bool


class HealthChecker:
    def __init__(
        self,
        registry: ProtocolRegistry,
        alert_dispatcher: AlertDispatcher | None = None,
        db_connection: aiosqlite.Connection | None = None,
    ) -> None:
        self.registry = registry
        self.alert_dispatcher = alert_dispatcher
        self._db = db_connection

    async def check_all(self) -> HealthReport:
        db_ok = await self._check_db()

        protocols: dict[ProtocolType, bool] = {}

        for protocol in self.registry.list_registered():
            adapter = self.registry.get(protocol)
            if adapter is None:
                protocols[protocol] = False
                continue
            try:
                health = await adapter.health()
                protocols[protocol] = health.healthy
                if not health.healthy and self.alert_dispatcher:
                    await self.alert_dispatcher.send(
                        Alert(
                            level=AlertLevel.WARNING,
                            title=f"{protocol.value} unhealthy",
                            message=health.message,
                            source="health_checker",
                        )
                    )
            except Exception:
                protocols[protocol] = False
                logger.exception(
                    "Health check failed",
                    extra={"protocol": protocol.value},
                )

        all_protocols_ok = (
            all(protocols.values()) if protocols else True
        )
        return HealthReport(
            bot_alive=True,
            db_healthy=db_ok,
            protocols=protocols,
            overall_healthy=all_protocols_ok and db_ok,
        )

    async def _check_db(self) -> bool:
        if self._db is None:
            return True
        try:
            cursor = await self._db.execute("SELECT 1")
            await cursor.fetchone()
            return True
        except Exception:
            logger.exception("Database health check failed")
            return False
