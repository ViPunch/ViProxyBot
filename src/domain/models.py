from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from src.domain.enums import ClientStatus, ProtocolStatus, ProtocolType


class ProtocolInstallation(BaseModel):
    protocol: ProtocolType
    status: ProtocolStatus
    listen_port: int
    service_name: str
    config_path: Path
    installed_at: datetime | None = None
    updated_at: datetime | None = None


class ClientAccount(BaseModel):
    id: int
    protocol: ProtocolType
    external_name: str
    status: ClientStatus
    created_at: datetime


class ClientCredential(BaseModel):
    id: int
    client_id: int
    protocol: ProtocolType
    uuid: str
    created_at: datetime


class TrafficSnapshot(BaseModel):
    id: int
    protocol: ProtocolType
    client_id: int | None = None
    rx_bytes: int
    tx_bytes: int
    collected_at: datetime


class AuditEvent(BaseModel):
    id: int
    actor_telegram_user_id: int
    action: str
    target_type: str
    target_id: str
    status: str
    details_redacted: str
    created_at: datetime
