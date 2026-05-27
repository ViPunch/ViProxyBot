from enum import StrEnum


class ProtocolType(StrEnum):
    VLESS = "vless"
    HYSTERIA2 = "hysteria2"
    MTPROTO = "mtproto"


class ProtocolStatus(StrEnum):
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


class ClientStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
