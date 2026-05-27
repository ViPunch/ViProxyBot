from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from src.domain.enums import ProtocolStatus


@dataclass(slots=True)
class InstallResult:
    success: bool
    service_name: str
    listen_port: int
    config_path: Path
    error: str | None = None


@dataclass(slots=True)
class HealthResult:
    healthy: bool
    status: str
    message: str


class ProtocolAdapter(ABC):
    @abstractmethod
    async def detect(self) -> ProtocolStatus:
        raise NotImplementedError

    @abstractmethod
    async def install(self, listen_port: int, public_host: str) -> InstallResult:
        raise NotImplementedError

    @abstractmethod
    async def create_client(self, external_name: str) -> tuple[str, str]:
        raise NotImplementedError

    @abstractmethod
    async def delete_client(self, identifier: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def reload_service(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> HealthResult:
        raise NotImplementedError

    @abstractmethod
    async def backup_config(self) -> str | None:
        raise NotImplementedError
