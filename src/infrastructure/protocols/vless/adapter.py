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
XRAY_CONFIG_DIR = Path("/usr/local/etc/xray")
XRAY_CONFIG_PATH = XRAY_CONFIG_DIR / "config.json"
XRAY_INSTALL_URL = (
    "https://github.com/XTLS/Xray-install/raw/main/install-release.sh"
)
VLESS_REALITY_SNI = "www.microsoft.com"


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
        self._listen_port: int = 443
        self._private_key: str = ""
        self._public_key: str = ""
        self._short_id: str = ""
        self._sni_domain: str = VLESS_REALITY_SNI

    async def detect(self) -> ProtocolStatus:
        if not Path(XRAY_BINARY).exists():
            return ProtocolStatus.NOT_INSTALLED
        if not self.config_path.exists():
            return ProtocolStatus.NOT_INSTALLED
        try:
            result = await run_command(
                ["systemctl", "is-active", self.service_name]
            )
            if result.success and result.stdout == "active":
                return ProtocolStatus.ACTIVE
            return ProtocolStatus.DEGRADED
        except FileNotFoundError:
            return ProtocolStatus.NOT_INSTALLED

    async def install(self, listen_port: int, public_host: str) -> InstallResult:
        self.public_host = public_host
        self._listen_port = listen_port

        if not Path(XRAY_BINARY).exists():
            await self._install_xray()

        await self._generate_reality_keys()

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_reality_config(listen_port)

        await self._write_systemd_unit()
        await run_command(
            ["sudo", "systemctl", "daemon-reload"]
        )
        await run_command(
            ["sudo", "systemctl", "enable", self.service_name]
        )
        await run_command(
            ["sudo", "systemctl", "restart", self.service_name]
        )

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
        updated_config = add_client_to_config(
            config, credential, external_name
        )
        save_config(self.config_path, updated_config)
        if not await self.reload_service():
            raise ServiceReloadError("Failed to reload xray service")
        return credential, external_name

    async def delete_client(self, identifier: str) -> None:
        config = load_config(self.config_path)
        clients = get_clients_from_config(config)
        if not any(
            client.get("email") == identifier for client in clients
        ):
            raise ClientNotFoundError(identifier)
        updated_config = remove_client_from_config(config, identifier)
        save_config(self.config_path, updated_config)
        if not await self.reload_service():
            raise ServiceReloadError("Failed to reload xray service")

    async def reload_service(self) -> bool:
        try:
            result = await run_command(
                ["sudo", "systemctl", "restart", self.service_name]
            )
            return result.success
        except FileNotFoundError:
            return False

    async def health(self) -> HealthResult:
        try:
            result = await run_command(
                ["systemctl", "is-active", self.service_name]
            )
            healthy = result.success and result.stdout == "active"
            status = result.stdout if result.stdout else "unknown"
            message = (
                "Service is active"
                if healthy
                else result.stderr or "Service is not active"
            )
            return HealthResult(
                healthy=healthy, status=status, message=message
            )
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
        backup_path = (
            self.backups_dir / f"xray-config-{timestamp}.json"
        )
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
                    public_key=self._public_key,
                    short_id=self._short_id,
                    sni=self._sni_domain or VLESS_REALITY_SNI,
                )
        raise ClientNotFoundError(email)

    async def _install_xray(self) -> None:
        logger.info("Installing Xray-core via official script")
        result = await run_command(
            [
                "sudo", "bash", "-c",
                f"curl -L {XRAY_INSTALL_URL} | bash -s -- install",
            ],
            timeout=180.0,
        )
        if not result.success:
            logger.error(
                "Xray install failed: %s", result.stderr
            )
            raise RuntimeError(
                f"Xray installation failed: {result.stderr}"
            )

    async def _generate_reality_keys(self) -> None:
        logger.info("Generating REALITY keys")
        result = await run_command(
            [XRAY_BINARY, "x25519"]
        )
        if not result.success:
            raise RuntimeError("Failed to generate REALITY keys")

        for line in result.stdout.splitlines():
            if "Private key:" in line:
                self._private_key = line.split(":", 1)[1].strip()
            elif "Public key:" in line:
                self._public_key = line.split(":", 1)[1].strip()

        self._short_id = uuid.uuid4().hex[:16]

        if not self._private_key or not self._public_key:
            raise RuntimeError("Failed to parse REALITY keys")

    def _create_reality_config(self, listen_port: int) -> None:
        sni = self._sni_domain or VLESS_REALITY_SNI
        config = {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {
                    "port": listen_port,
                    "protocol": "vless",
                    "settings": {
                        "clients": [],
                        "decryption": "none",
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "show": False,
                            "dest": f"{sni}:443",
                            "xver": 0,
                            "serverNames": [
                                sni,
                                f"www.{sni}",
                            ],
                            "privateKey": self._private_key,
                            "shortIds": [self._short_id],
                        },
                    },
                    "sniffing": {
                        "enabled": True,
                        "destOverride": ["http", "tls"],
                    },
                }
            ],
            "outbounds": [
                {"protocol": "freedom", "tag": "direct"},
                {"protocol": "blackhole", "tag": "block"},
            ],
        }
        save_config(self.config_path, config)

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
        tmp_path = "/tmp/vpnbot-xray.service"
        Path(tmp_path).write_text(unit, encoding="utf-8")
        await run_command(
            ["sudo", "cp", tmp_path, XRAY_SERVICE]
        )

    async def _open_port(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(
                ["sudo", "ufw", "allow", str(port)]
            )
