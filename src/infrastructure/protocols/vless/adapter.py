from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from src.domain.enums import ProtocolStatus
from src.domain.exceptions import ClientNotFoundError, ServiceReloadError
from src.infrastructure.protocols.base import (
    HealthResult,
    InstallResult,
    ProtocolAdapter,
)
from src.infrastructure.protocols.vless.config_writer import (
    add_client_to_config,
    create_initial_config,
    get_clients_from_config,
    get_listen_port_from_config,
    load_config,
    remove_client_from_config,
    save_config,
)
from src.infrastructure.protocols.vless.link_generator import generate_vless_link
from src.infrastructure.shell_runner import run_command

logger = logging.getLogger(__name__)

XRAY_BINARY = "/usr/local/bin/xray"
XRAY_SERVICE = "/etc/systemd/system/xray.service"
XRAY_INSTALL_URL = (
    "https://github.com/XTLS/Xray-core/releases/latest/download/"
    "Xray-linux-64.zip"
)


class VlessAdapter(ProtocolAdapter):
    def __init__(
        self,
        config_path: Path,
        backups_dir: Path,
        public_host: str,
    ) -> None:
        self.config_path = config_path
        self.backups_dir = backups_dir
        self.public_host = public_host
        self.service_name = "xray"

    async def detect(self) -> ProtocolStatus:
        if not self.config_path.exists():
            return ProtocolStatus.NOT_INSTALLED
        try:
            result = await run_command(["systemctl", "is-active", self.service_name])
            if result.success and result.stdout == "active":
                return ProtocolStatus.ACTIVE
            return ProtocolStatus.DEGRADED
        except FileNotFoundError:
            return ProtocolStatus.NOT_INSTALLED

    async def install(self, listen_port: int, public_host: str) -> InstallResult:
        self.public_host = public_host

        if not Path(XRAY_BINARY).exists():
            await self._download_xray()

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        create_initial_config(self.config_path, listen_port)

        await self._write_systemd_unit()
        await run_command(["systemctl", "daemon-reload"])
        await run_command(["systemctl", "enable", self.service_name])
        await run_command(["systemctl", "restart", self.service_name])

        await self._open_port(listen_port)

        return InstallResult(
            success=True,
            service_name=self.service_name,
            listen_port=listen_port,
            config_path=self.config_path,
        )

    async def create_client(self, external_name: str) -> tuple[str, str]:
        config = load_config(self.config_path)
        credential = str(uuid.uuid4())
        updated_config = add_client_to_config(config, credential, external_name)
        save_config(self.config_path, updated_config)
        if not await self.reload_service():
            raise ServiceReloadError("Failed to reload xray service")
        return credential, external_name

    async def delete_client(self, identifier: str) -> None:
        config = load_config(self.config_path)
        clients = get_clients_from_config(config)
        if not any(client.get("email") == identifier for client in clients):
            raise ClientNotFoundError(identifier)
        updated_config = remove_client_from_config(config, identifier)
        save_config(self.config_path, updated_config)
        if not await self.reload_service():
            raise ServiceReloadError("Failed to reload xray service")

    async def reload_service(self) -> bool:
        try:
            result = await run_command(["systemctl", "restart", self.service_name])
            return result.success
        except FileNotFoundError:
            return False

    async def health(self) -> HealthResult:
        try:
            result = await run_command(["systemctl", "is-active", self.service_name])
            healthy = result.success and result.stdout == "active"
            status = result.stdout if result.stdout else "unknown"
            message = (
                "Service is active"
                if healthy
                else result.stderr or "Service is not active"
            )
            return HealthResult(healthy=healthy, status=status, message=message)
        except FileNotFoundError:
            return HealthResult(
                healthy=False,
                status="unknown",
                message="systemctl not available",
            )

    async def backup_config(self) -> str | None:
        if not self.config_path.exists():
            return None
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = self.backups_dir / f"xray-config-{timestamp}.json"
        shutil.copy2(self.config_path, backup_path)
        return str(backup_path)

    def generate_link(self, email: str) -> str:
        config = load_config(self.config_path)
        for client in get_clients_from_config(config):
            if client.get("email") == email:
                return generate_vless_link(
                    client["id"],
                    self.public_host,
                    get_listen_port_from_config(config),
                    remark=email,
                )
        raise ClientNotFoundError(email)

    async def _download_xray(self) -> None:
        logger.info("Downloading Xray-core")
        await run_command(
            [
                "bash",
                "-c",
                f"curl -sL {XRAY_INSTALL_URL} -o /tmp/xray.zip "
                f"&& unzip -o /tmp/xray.zip xray -d /usr/local/bin/ "
                f"&& chmod +x {XRAY_BINARY}",
            ],
            timeout=120.0,
        )

    async def _write_systemd_unit(self) -> None:
        unit = (
            "[Unit]\n"
            "Description=Xray Service\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"ExecStart={XRAY_BINARY} run -config {self.config_path}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        Path(XRAY_SERVICE).write_text(unit, encoding="utf-8")

    async def _open_port(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(["ufw", "allow", str(port)])
