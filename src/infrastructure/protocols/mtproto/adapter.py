from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from src.domain.enums import ProtocolStatus
from src.infrastructure.protocols.base import (
    HealthResult,
    InstallResult,
    ProtocolAdapter,
)
from src.infrastructure.protocols.mtproto.link_generator import (
    generate_mtproto_link,
)
from src.infrastructure.shell_runner import run_command

logger = logging.getLogger(__name__)

MTPROTO_DIR = Path("/opt/MTProxy")
MTPROTO_BINARY = MTPROTO_DIR / "objs" / "bin" / "mtproto-proxy"
MTPROTO_SERVICE = "/etc/systemd/system/mtproxy.service"
MTPROTO_SECRET_PATH = MTPROTO_DIR / "proxy-secret"
MTPROTO_CONFIG_PATH = MTPROTO_DIR / "proxy-multi.conf"
MTPROTO_REPO = "https://github.com/TelegramMessenger/MTProxy"


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
        self._secret: str = ""
        self._listen_port: int = 443

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

    async def install(self, listen_port: int, public_host: str) -> InstallResult:
        self.public_host = public_host
        self._listen_port = listen_port

        if not MTPROTO_BINARY.exists():
            await self._build_mtproto()

        await self._download_proxy_data()

        self._secret = uuid.uuid4().hex
        self.config_dir.mkdir(parents=True, exist_ok=True)
        secret_path = self.config_dir / "mtproxy.secret"
        secret_path.write_text(self._secret, encoding="utf-8")

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
            config_path=secret_path,
        )

    async def create_client(self, external_name: str) -> tuple[str, str]:
        config_path = self.config_dir / "mtproxy.secret"
        if config_path.exists():
            self._secret = config_path.read_text(
                encoding="utf-8"
            ).strip()
        else:
            self._secret = uuid.uuid4().hex
            config_path.write_text(self._secret, encoding="utf-8")
        return self._secret, external_name

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
        if not self.config_dir.exists():
            return None
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = (
            self.backups_dir / f"mtproto-config-{timestamp}"
        )
        shutil.copytree(
            self.config_dir, backup_path, dirs_exist_ok=True
        )
        return str(backup_path)

    def generate_link(self, label: str) -> str:
        config_path = self.config_dir / "mtproxy.secret"
        if config_path.exists():
            self._secret = config_path.read_text(
                encoding="utf-8"
            ).strip()
        return generate_mtproto_link(
            self.public_host, self._listen_port, self._secret
        )

    async def _build_mtproto(self) -> None:
        logger.info("Building MTProxy from source")
        await run_command(
            [
                "sudo", "apt-get", "install", "-y",
                "git", "curl", "build-essential",
                "libssl-dev", "zlib1g-dev",
            ],
            timeout=120.0,
        )
        if MTPROTO_DIR.exists():
            await run_command(
                ["sudo", "rm", "-rf", str(MTPROTO_DIR)]
            )
        await run_command(
            [
                "sudo", "git", "clone",
                MTPROTO_REPO, str(MTPROTO_DIR),
            ],
            timeout=120.0,
        )
        result = await run_command(
            ["sudo", "make", "-C", str(MTPROTO_DIR)],
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
                "sudo", "bash", "-c",
                "curl -s https://core.telegram.org/getProxySecret "
                f"-o {MTPROTO_SECRET_PATH}",
            ],
            timeout=30.0,
        )
        await run_command(
            [
                "sudo", "bash", "-c",
                "curl -s https://core.telegram.org/getProxyConfig "
                f"-o {MTPROTO_CONFIG_PATH}",
            ],
            timeout=30.0,
        )

    async def _write_systemd_unit(self) -> None:
        unit = (
            "[Unit]\n"
            "Description=MTProxy Service\n"
            "After=network.target\n\n"
            "[Service]\n"
            f"WorkingDirectory={MTPROTO_DIR}\n"
            f"ExecStart={MTPROTO_BINARY} "
            f"-u nobody -p 8888 -H {self._listen_port} "
            f"-S {self._secret} "
            f"--aes-pwd {MTPROTO_SECRET_PATH} "
            f"{MTPROTO_CONFIG_PATH} -M 1\n"
            "Restart=on-failure\n"
            "RestartSec=5\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        tmp_path = "/tmp/vpnbot-mtproxy.service"
        Path(tmp_path).write_text(unit, encoding="utf-8")
        await run_command(
            ["sudo", "cp", tmp_path, MTPROTO_SERVICE]
        )

    async def _open_port(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(
                ["sudo", "ufw", "allow", str(port)]
            )
