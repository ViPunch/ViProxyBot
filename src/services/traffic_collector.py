from __future__ import annotations

import logging

from src.database.repositories import TrafficRepository
from src.domain.enums import ProtocolType
from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)


class TrafficCollector:
    def __init__(
        self,
        registry: ProtocolRegistry,
        traffic_repo: TrafficRepository,
    ) -> None:
        self.registry = registry
        self.traffic_repo = traffic_repo

    async def collect_all(self) -> None:
        for protocol in self.registry.list_registered():
            await self.collect_protocol(protocol)

    async def collect_protocol(self, protocol: ProtocolType) -> None:
        adapter = self.registry.get(protocol)
        if adapter is None:
            return

        try:
            if hasattr(adapter, "collect_traffic"):
                traffic_data = await adapter.collect_traffic()
                for client_name, stats in traffic_data.items():
                    await self.traffic_repo.save_snapshot(
                        protocol=protocol,
                        client_name=client_name,
                        rx_bytes=stats.get("rx", 0),
                        tx_bytes=stats.get("tx", 0),
                    )
        except Exception:
            logger.exception(
                "Traffic collection failed",
                extra={"protocol": protocol.value},
            )
