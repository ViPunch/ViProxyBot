from __future__ import annotations

from dataclasses import dataclass

from src.domain.enums import ProtocolType


@dataclass(frozen=True)
class ProtocolCapabilities:
    supports_individual_clients: bool
    supports_client_link_generation: bool
    supports_per_client_traffic: bool
    supports_aggregate_traffic: bool
    supports_hot_reload: bool
    supports_backup_restore: bool
    supports_port_change: bool


CAPABILITY_MATRIX: dict[ProtocolType, ProtocolCapabilities] = {
    ProtocolType.VLESS: ProtocolCapabilities(
        supports_individual_clients=True,
        supports_client_link_generation=True,
        supports_per_client_traffic=True,
        supports_aggregate_traffic=True,
        supports_hot_reload=True,
        supports_backup_restore=True,
        supports_port_change=True,
    ),
    ProtocolType.HYSTERIA2: ProtocolCapabilities(
        supports_individual_clients=True,
        supports_client_link_generation=True,
        supports_per_client_traffic=True,
        supports_aggregate_traffic=True,
        supports_hot_reload=True,
        supports_backup_restore=True,
        supports_port_change=True,
    ),
    ProtocolType.MTPROTO: ProtocolCapabilities(
        supports_individual_clients=False,
        supports_client_link_generation=True,
        supports_per_client_traffic=False,
        supports_aggregate_traffic=True,
        supports_hot_reload=False,
        supports_backup_restore=True,
        supports_port_change=True,
    ),
}


def get_capabilities(protocol: ProtocolType) -> ProtocolCapabilities:
    return CAPABILITY_MATRIX[protocol]
