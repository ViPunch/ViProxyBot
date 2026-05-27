from __future__ import annotations

from src.domain.capability import ProtocolCapabilities, get_capabilities
from src.domain.enums import ProtocolType
from src.infrastructure.protocols.base import ProtocolAdapter


class ProtocolRegistry:
    def __init__(self) -> None:
        self._adapters: dict[ProtocolType, ProtocolAdapter] = {}

    def register(
        self,
        protocol: ProtocolType,
        adapter: ProtocolAdapter,
    ) -> None:
        self._adapters[protocol] = adapter

    def get(self, protocol: ProtocolType) -> ProtocolAdapter | None:
        return self._adapters.get(protocol)

    def list_protocols(self) -> list[ProtocolType]:
        return list(self._adapters.keys())

    def list_registered(self) -> list[ProtocolType]:
        return list(self._adapters.keys())

    def is_registered(self, protocol: ProtocolType) -> bool:
        return protocol in self._adapters

    def get_capabilities(
        self,
        protocol: ProtocolType,
    ) -> ProtocolCapabilities:
        return get_capabilities(protocol)
