from __future__ import annotations

import logging
from dataclasses import dataclass

from src.domain.enums import ProtocolType
from src.infrastructure.alerting import Alert, AlertDispatcher, AlertLevel
from src.services.protocol_registry import ProtocolRegistry

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
    ) -> None:
        self.registry = registry
        self.alert_dispatcher = alert_dispatcher

    async def check_all(self) -> HealthReport:
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

        all_ok = all(protocols.values()) if protocols else True
        return HealthReport(
            bot_alive=True,
            db_healthy=True,
            protocols=protocols,
            overall_healthy=all_ok,
        )
