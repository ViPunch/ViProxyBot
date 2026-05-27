from src.domain.enums import ClientStatus, ProtocolStatus, ProtocolType


def test_protocol_type_values() -> None:
    assert ProtocolType.VLESS == 'vless'
    assert ProtocolType.HYSTERIA2 == 'hysteria2'
    assert ProtocolType.MTPROTO == 'mtproto'


def test_protocol_status_values() -> None:
    assert ProtocolStatus.NOT_INSTALLED == 'not_installed'
    assert ProtocolStatus.INSTALLING == 'installing'
    assert ProtocolStatus.ACTIVE == 'active'
    assert ProtocolStatus.DEGRADED == 'degraded'
    assert ProtocolStatus.FAILED == 'failed'
    assert ProtocolStatus.DISABLED == 'disabled'
    assert ClientStatus.ACTIVE == 'active'
    assert ClientStatus.REVOKED == 'revoked'
