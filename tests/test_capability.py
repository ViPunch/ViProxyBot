from src.domain.capability import get_capabilities
from src.domain.enums import ProtocolType


def test_vless_capabilities() -> None:
    caps = get_capabilities(ProtocolType.VLESS)
    assert caps.supports_individual_clients is True
    assert caps.supports_client_link_generation is True
    assert caps.supports_per_client_traffic is True
    assert caps.supports_aggregate_traffic is True
    assert caps.supports_hot_reload is True
    assert caps.supports_backup_restore is True
    assert caps.supports_port_change is True


def test_hysteria2_capabilities() -> None:
    caps = get_capabilities(ProtocolType.HYSTERIA2)
    assert caps.supports_individual_clients is True
    assert caps.supports_per_client_traffic is True
