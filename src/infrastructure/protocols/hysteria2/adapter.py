from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.domain.enums import ProtocolStatus
from src.domain.exceptions import ServiceReloadError
from src.infrastructure.http_client import http_get_json
from src.infrastructure.protocols.base import (
    HealthResult,
    InstallResult,
    ProtocolAdapter,
)
from src.infrastructure.protocols.hysteria2.config_writer import (
    create_server_config,
    get_auth_password,
    get_listen_port,
    get_stats_endpoint,
    get_stats_secret,
    load_config,
    save_config,
    update_auth_password,
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
HYSTERIA_INSTALL_SCRIPT = "https://get.hy2.sh/"
VPNBOT_CTL = "/usr/local/bin/vpnbot-ctl"


class Hysteria2Adapter(ProtocolAdapter):
    def __init__(
        self,
        config_path: Path,
        backups_dir: Path,
        public_host: str,
        cert_path: str = "",
        key_path: str = "",
    ) -> None:
        self.config_path = config_path
        self.backups_dir = backups_dir
        self.public_host = public_host
        self.service_name = "hysteria"
        self._cert_path = cert_path
        self._key_path = key_path
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

    async def install(
        self, listen_port: int, public_host: str
    ) -> InstallResult:
        self.public_host = public_host
        self._listen_port = listen_port

        if not Path(HYSTERIA_BINARY).exists():
            await self._install_hysteria()

        self._auth_password = str(uuid.uuid4())
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        cert_path, key_path = await self._resolve_cert_paths(public_host)

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
            ["sudo", VPNBOT_CTL, "service", "reload", "_"]
        )
        await run_command(
            ["sudo", VPNBOT_CTL, "service", "enable", self.service_name]
        )
        if not await self.reload_service():
            raise ServiceReloadError(
                "Failed to start hysteria after install"
            )

        await self._open_port_udp(listen_port)

        return InstallResult(
            success=True,
            service_name=self.service_name,
            listen_port=listen_port,
            config_path=self.config_path,
        )

    async def create_client(
        self, external_name: str
    ) -> tuple[str, str]:
        if not self.config_path.exists():
            raise ServiceReloadError("Hysteria2 config not found")

        await self.backup_config()

        config = load_config(self.config_path)
        password = get_auth_password(config)
        if not password:
            password = str(uuid.uuid4())
            updated = update_auth_password(config, password)
            save_config(self.config_path, updated)

            if not await self._validate_and_restart():
                raise ServiceReloadError(
                    "Hysteria2 restart failed after client creation"
                )

        return password, external_name

    async def delete_client(self, identifier: str) -> None:
        if not self.config_path.exists():
            raise ServiceReloadError("Hysteria2 config not found")

        await self.backup_config()

        config = load_config(self.config_path)
        new_password = str(uuid.uuid4())
        updated = update_auth_password(config, new_password)
        save_config(self.config_path, updated)

        if not await self._validate_and_restart():
            raise ServiceReloadError(
                "Hysteria2 restart failed after client deletion"
            )

    async def reload_service(self) -> bool:
        try:
            result = await run_command(
                ["sudo", VPNBOT_CTL, "service", "restart", self.service_name]
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
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = (
            self.backups_dir / f"hysteria-config-{timestamp}.yaml"
        )
        shutil.copy2(self.config_path, backup_path)
        return str(backup_path)

    def generate_link(self, label: str) -> str:
        if not self.config_path.exists():
            raise ServiceReloadError("Hysteria2 config not found")
        config = load_config(self.config_path)
        password = get_auth_password(config)
        port = get_listen_port(config)
        insecure = not self._cert_path
        return generate_hysteria2_uri(
            self.public_host,
            port,
            password,
            remark=label,
            insecure=insecure,
        )

    def generate_client_config(self, label: str) -> str:
        if not self.config_path.exists():
            raise ServiceReloadError("Hysteria2 config not found")
        config = load_config(self.config_path)
        password = get_auth_password(config)
        port = get_listen_port(config)
        insecure = not self._cert_path
        return generate_hysteria2_client_config_text(
            self.public_host,
            port,
            password,
            insecure=insecure,
        )

    async def collect_traffic(self) -> dict[str, dict[str, int]]:
        if not self.config_path.exists():
            return {}
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

    async def _resolve_cert_paths(
        self, public_host: str
    ) -> tuple[str, str]:
        if self._cert_path and self._key_path:
            if Path(self._cert_path).exists() and Path(
                self._key_path
            ).exists():
                return self._cert_path, self._key_path

        domain = self._sni_domain or public_host
        await self._generate_tls_certs(domain)
        return (
            str(HYSTERIA_CONFIG_DIR / "cert.pem"),
            str(HYSTERIA_CONFIG_DIR / "key.pem"),
        )

    async def _validate_and_restart(self) -> bool:
        validate_result = await run_command(
            [
                "sudo", VPNBOT_CTL,
                "file", "chmod", "644", str(self.config_path),
            ],
            timeout=5.0,
        )
        if not validate_result.success:
            logger.warning("Could not verify config permissions")

        restart_ok = await self.reload_service()
        if not restart_ok:
            logger.error("Hysteria2 restart failed, rolling back")
            await self._rollback_config()
            return False

        return True

    async def _rollback_config(self) -> None:
        if not self.backups_dir.exists():
            return
        backups = sorted(
            self.backups_dir.glob("hysteria-config-*.yaml"),
            reverse=True,
        )
        if not backups:
            return
        latest = backups[0]
        logger.warning("Rolling back Hysteria2 config from %s", latest)
        shutil.copy2(latest, self.config_path)
        await self.reload_service()

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
            logger.error("Hysteria2 install failed: %s", result.stderr)
            raise RuntimeError(
                f"Hysteria2 installation failed: {result.stderr}"
            )

    async def _generate_tls_certs(self, domain: str) -> None:
        logger.info("Generating self-signed TLS certificates")
        await run_command(
            ["sudo", VPNBOT_CTL, "file", "mkdir", str(HYSTERIA_CONFIG_DIR)]
        )
        await run_command(
            [
                "sudo", VPNBOT_CTL,
                "cert", "selfsigned", domain, str(HYSTERIA_CONFIG_DIR),
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
            ["sudo", VPNBOT_CTL, "file", "cp", tmp_path, HYSTERIA_SERVICE]
        )

    async def _open_port_udp(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(
                ["sudo", VPNBOT_CTL, "firewall", "allow", f"{port}/udp"]
            )
