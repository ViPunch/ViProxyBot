from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.domain.enums import ProtocolStatus
from src.domain.exceptions import ClientNotFoundError, ServiceReloadError
from src.infrastructure.protocols.base import (
    HealthResult,
    InstallResult,
    ProtocolAdapter,
)
from src.infrastructure.protocols.mtproto.link_generator import (
    generate_mtproto_link,
    generate_mtproto_tg_link,
)
from src.infrastructure.shell_runner import run_command

logger = logging.getLogger(__name__)

MTPROTO_DIR = Path("/opt/MTProxy")
MTPROTO_BINARY = MTPROTO_DIR / "objs" / "bin" / "mtproto-proxy"
MTPROTO_SERVICE = "/etc/systemd/system/mtproxy.service"
MTPROTO_SECRET_PATH = MTPROTO_DIR / "proxy-secret"
MTPROTO_CONFIG_PATH = MTPROTO_DIR / "proxy-multi.conf"
MTPROTO_REPO = "https://github.com/TelegramMessenger/MTProxy"
VPNBOT_CTL = "/usr/local/bin/vpnbot-ctl"

SECRETS_FILE = "mtproxy.secrets.json"
STATS_URL = "http://127.0.0.1:8888/stats"


class MtprotoAdapter(ProtocolAdapter):
    def __init__(
        self,
        config_dir: Path,
        backups_dir: Path,
        public_host: str,
    ) -> None:
        self.config_dir = config_dir
        self.backups_dir = backups_dir
        self.public_host = public_host
        self.service_name = "mtproxy"
        self._secrets: dict[str, str] = {}
        self._listen_port: int = 8443
        self._proxy_tag: str = ""
        self._load_secrets()

    def _secrets_path(self) -> Path:
        return self.config_dir / SECRETS_FILE

    def _load_secrets(self) -> None:
        path = self._secrets_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._secrets = data.get("secrets", {})
            self._proxy_tag = data.get("proxy_tag", "")
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load MTProto secrets from %s", path)

    def _save_secrets(self) -> None:
        path = self._secrets_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "secrets": self._secrets,
            "proxy_tag": self._proxy_tag,
        }
        path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )

    def _get_primary_secret(self) -> str:
        if self._secrets:
            return next(iter(self._secrets.values()))
        return ""

    async def detect(self) -> ProtocolStatus:
        if not MTPROTO_BINARY.exists():
            return ProtocolStatus.NOT_INSTALLED
        try:
            result = await run_command(
                ["systemctl", "is-active", self.service_name]
            )
            if result.success and result.stdout == "active":
                return ProtocolStatus.ACTIVE
            return ProtocolStatus.DEGRADED
        except FileNotFoundError:
            if MTPROTO_DIR.exists():
                return ProtocolStatus.DEGRADED
            return ProtocolStatus.NOT_INSTALLED

    async def install(
        self, listen_port: int, public_host: str
    ) -> InstallResult:
        self.public_host = public_host
        self._listen_port = listen_port

        if not MTPROTO_BINARY.exists():
            await self._build_mtproto()

        await self._download_proxy_data()

        secret = uuid.uuid4().hex
        self._secrets = {f"user-{secret[:8]}": secret}
        self._save_secrets()

        await self._write_systemd_unit()
        await run_command(
            ["sudo", VPNBOT_CTL, "service", "reload", "_"]
        )
        await run_command(
            ["sudo", VPNBOT_CTL, "service", "enable", self.service_name]
        )
        if not await self.reload_service():
            raise ServiceReloadError(
                "Failed to start MTProxy after install"
            )

        await self._open_port(listen_port)

        secret_path = self.config_dir / "mtproxy.secret"
        secret_path.write_text(secret, encoding="utf-8")

        return InstallResult(
            success=True,
            service_name=self.service_name,
            listen_port=listen_port,
            config_path=secret_path,
        )

    async def create_client(
        self, external_name: str
    ) -> tuple[str, str]:
        await self.backup_config()

        secret = uuid.uuid4().hex
        self._secrets[external_name] = secret
        self._save_secrets()

        if not await self._validate_and_restart():
            raise ServiceReloadError(
                "MTProxy restart failed after client creation"
            )

        secret_path = self.config_dir / "mtproxy.secret"
        secret_path.write_text(secret, encoding="utf-8")

        return secret, external_name

    async def delete_client(self, identifier: str) -> None:
        if identifier not in self._secrets:
            raise ClientNotFoundError(identifier)

        await self.backup_config()

        del self._secrets[identifier]
        self._save_secrets()

        if not await self._validate_and_restart():
            raise ServiceReloadError(
                "MTProxy restart failed after client deletion"
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
        if not self.config_dir.exists():
            return None
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = (
            self.backups_dir / f"mtproto-config-{timestamp}"
        )
        shutil.copytree(
            self.config_dir, backup_path, dirs_exist_ok=True
        )
        return str(backup_path)

    def generate_link(self, label: str) -> str:
        secret = self._get_primary_secret()
        if not secret:
            secret_path = self.config_dir / "mtproxy.secret"
            if secret_path.exists():
                secret = secret_path.read_text(encoding="utf-8").strip()
        if not secret:
            raise ClientNotFoundError("No MTProto secret available")
        return generate_mtproto_link(
            self.public_host, self._listen_port, secret
        )

    def generate_tg_link(self, label: str) -> str:
        secret = self._get_primary_secret()
        if not secret:
            raise ClientNotFoundError("No MTProto secret available")
        return generate_mtproto_tg_link(
            self.public_host, self._listen_port, secret
        )

    async def collect_traffic(self) -> dict[str, dict[str, int]]:
        return {}

    async def refresh_proxy_config(self) -> bool:
        logger.info("Refreshing MTProxy proxy-multi.conf")
        result = await run_command(
            [
                "sudo", VPNBOT_CTL, "curl-dl", "download",
                "https://core.telegram.org/getProxyConfig",
                str(MTPROTO_CONFIG_PATH),
            ],
            timeout=30.0,
        )
        if result.success:
            await self.reload_service()
        return result.success

    async def _validate_and_restart(self) -> bool:
        restart_ok = await self.reload_service()
        if not restart_ok:
            logger.error("MTProxy restart failed, rolling back")
            await self._rollback_config()
            return False
        return True

    async def _rollback_config(self) -> None:
        if not self.backups_dir.exists():
            return
        backups = sorted(
            self.backups_dir.glob("mtproto-config-*"),
            reverse=True,
        )
        if not backups:
            return
        latest = backups[0]
        logger.warning("Rolling back MTProto config from %s", latest)
        shutil.copytree(latest, self.config_dir, dirs_exist_ok=True)
        await self.reload_service()

    async def _build_mtproto(self) -> None:
        logger.info("Building MTProxy from source")
        await run_command(
            [
                "sudo", VPNBOT_CTL, "pkg", "install",
                "git", "curl", "build-essential",
                "libssl-dev", "zlib1g-dev",
            ],
            timeout=120.0,
        )
        if MTPROTO_DIR.exists():
            await run_command(
                ["sudo", VPNBOT_CTL, "file", "rm", str(MTPROTO_DIR)]
            )
        await run_command(
            [
                "sudo", VPNBOT_CTL, "git", "clone",
                MTPROTO_REPO, str(MTPROTO_DIR),
            ],
            timeout=120.0,
        )
        result = await run_command(
            ["sudo", VPNBOT_CTL, "make", "build", str(MTPROTO_DIR)],
            timeout=300.0,
        )
        if not result.success:
            raise RuntimeError(
                f"MTProxy build failed: {result.stderr}"
            )

    async def _download_proxy_data(self) -> None:
        logger.info("Downloading MTProxy data")
        await run_command(
            [
                "sudo", VPNBOT_CTL, "curl-dl", "download",
                "https://core.telegram.org/getProxySecret",
                str(MTPROTO_SECRET_PATH),
            ],
            timeout=30.0,
        )
        await run_command(
            [
                "sudo", VPNBOT_CTL, "curl-dl", "download",
                "https://core.telegram.org/getProxyConfig",
                str(MTPROTO_CONFIG_PATH),
            ],
            timeout=30.0,
        )

    async def _write_systemd_unit(self) -> None:
        primary = self._get_primary_secret()
        tag_arg = f" -T {self._proxy_tag}" if self._proxy_tag else ""
        unit = (
            "[Unit]\n"
            "Description=MTProxy Service\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={MTPROTO_DIR}\n"
            f"ExecStart={MTPROTO_BINARY} "
            f"-u nobody -p 8888 -H {self._listen_port} "
            f"-S {primary} "
            f"--aes-pwd {MTPROTO_SECRET_PATH} "
            f"{MTPROTO_CONFIG_PATH} -M 1{tag_arg}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        tmp_path = "/tmp/vpnbot-mtproxy.service"
        Path(tmp_path).write_text(unit, encoding="utf-8")
        await run_command(
            ["sudo", VPNBOT_CTL, "file", "cp", tmp_path, MTPROTO_SERVICE]
        )

    async def _open_port(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(
                ["sudo", VPNBOT_CTL, "firewall", "allow", str(port)]
            )
