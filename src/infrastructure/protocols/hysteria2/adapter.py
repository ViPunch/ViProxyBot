from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from src.domain.enums import ProtocolStatus
from src.infrastructure.http_client import http_get_json
from src.infrastructure.protocols.base import (
    HealthResult,
    InstallResult,
    ProtocolAdapter,
)
from src.infrastructure.protocols.hysteria2.config_writer import (
    create_server_config,
    get_auth_password,
    get_stats_endpoint,
    get_stats_secret,
    load_config,
)
from src.infrastructure.protocols.hysteria2.link_generator import (
    generate_hysteria2_client_config_text,
    generate_hysteria2_uri,
)
from src.infrastructure.shell_runner import run_command

logger = logging.getLogger(__name__)

HYSTERIA_BINARY = "/usr/local/bin/hysteria"
HYSTERIA_SERVICE = "/etc/systemd/system/hysteria.service"
HYSTERIA_CONFIG_DIR = Path("/etc/hysteria")
HYSTERIA_CONFIG_PATH = HYSTERIA_CONFIG_DIR / "config.yaml"
HYSTERIA_INSTALL_SCRIPT = "https://get.hy2.sh/"


class Hysteria2Adapter(ProtocolAdapter):
    def __init__(
        self,
        config_path: Path,
        backups_dir: Path,
        public_host: str,
    ) -> None:
        self.config_path = config_path
        self.backups_dir = backups_dir
        self.public_host = public_host
        self.service_name = "hysteria"
        self._listen_port: int = 443
        self._auth_password: str = ""
        self._sni_domain: str = ""

    async def detect(self) -> ProtocolStatus:
        if not Path(HYSTERIA_BINARY).exists():
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

        if not Path(HYSTERIA_BINARY).exists():
            await self._install_hysteria()

        self._auth_password = str(uuid.uuid4())
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Use SSL cert paths if set, otherwise generate self-signed
        cert_path = getattr(self, "_cert_path", None)
        key_path = getattr(self, "_key_path", None)
        if not cert_path or not key_path:
            domain = self._sni_domain or public_host
            await self._generate_tls_certs(domain)
            cert_path = "/etc/hysteria/cert.pem"
            key_path = "/etc/hysteria/key.pem"

        create_server_config(
            self.config_path,
            listen_port,
            cert_path=cert_path,
            key_path=key_path,
            auth_password=self._auth_password,
            stats_listen="127.0.0.1:25199",
            stats_secret=str(uuid.uuid4()),
        )

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

        await self._open_port_udp(listen_port)

        return InstallResult(
            success=True,
            service_name=self.service_name,
            listen_port=listen_port,
            config_path=self.config_path,
        )

    async def create_client(self, external_name: str) -> tuple[str, str]:
        config = load_config(self.config_path)
        password = get_auth_password(config)
        return password, external_name

    async def delete_client(self, identifier: str) -> None:
        pass

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
            self.backups_dir / f"hysteria-config-{timestamp}.yaml"
        )
        shutil.copy2(self.config_path, backup_path)
        return str(backup_path)

    def generate_link(self, label: str) -> str:
        config = load_config(self.config_path)
        password = get_auth_password(config)
        port = _extract_port(config)
        return generate_hysteria2_uri(
            self.public_host,
            port,
            password,
            remark=label,
        )

    def generate_client_config(self, label: str) -> str:
        config = load_config(self.config_path)
        password = get_auth_password(config)
        port = _extract_port(config)
        return generate_hysteria2_client_config_text(
            self.public_host,
            port,
            password,
        )

    async def collect_traffic(self) -> dict[str, dict[str, int]]:
        config = load_config(self.config_path)
        endpoint = get_stats_endpoint(config)
        secret = get_stats_secret(config)
        if endpoint is None:
            return {}
        data = await http_get_json(
            f"{endpoint}/traffic",
            headers={"Authorization": secret} if secret else None,
        )
        if data is None or not isinstance(data, dict):
            return {}
        result: dict[str, dict[str, int]] = {}
        for user, stats in data.items():
            if isinstance(stats, dict):
                result[user] = {
                    "rx": int(stats.get("rx", 0)),
                    "tx": int(stats.get("tx", 0)),
                }
        return result

    async def _install_hysteria(self) -> None:
        logger.info("Installing Hysteria2 via official script")
        result = await run_command(
            [
                "sudo", "bash", "-c",
                f"curl -fsSL {HYSTERIA_INSTALL_SCRIPT} | bash",
            ],
            timeout=180.0,
        )
        if not result.success:
            logger.error(
                "Hysteria2 install failed: %s", result.stderr
            )
            raise RuntimeError(
                f"Hysteria2 installation failed: {result.stderr}"
            )

    async def _generate_tls_certs(self, domain: str) -> None:
        logger.info("Generating self-signed TLS certificates")
        cert_dir = Path("/etc/hysteria")
        await run_command(["sudo", "mkdir", "-p", str(cert_dir)])
        await run_command(
            [
                "sudo", "openssl", "req", "-x509", "-nodes",
                "-newkey", "ec",
                "-pkeyopt", "ec_paramgen_curve:prime256v1",
                "-days", "3650",
                "-keyout", "/etc/hysteria/key.pem",
                "-out", "/etc/hysteria/cert.pem",
                "-subj", f"/CN={domain}",
            ],
            timeout=30.0,
        )

    async def _write_systemd_unit(self) -> None:
        unit = (
            "[Unit]\n"
            "Description=Hysteria 2 Service\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"ExecStart={HYSTERIA_BINARY} server "
            f"-c {self.config_path}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        tmp_path = "/tmp/vpnbot-hysteria.service"
        Path(tmp_path).write_text(unit, encoding="utf-8")
        await run_command(
            ["sudo", "cp", tmp_path, HYSTERIA_SERVICE]
        )

    async def _open_port_udp(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(
                ["sudo", "ufw", "allow", f"{port}/udp"]
            )


def _extract_port(config: dict) -> int:
    listen = config.get("listen", ":443")
    if isinstance(listen, str) and listen.startswith(":"):
        return int(listen[1:])
    return int(listen)
