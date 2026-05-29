from __future__ import annotations

import json
import logging
import os
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
VLESS_REALITY_SNI = "www.microsoft.com"
VPNBOT_CTL = "/usr/local/bin/vpnbot-ctl"

REALITY_KEYS_FILE = "reality_keys.json"


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
        self._load_reality_keys()

    def _keys_path(self) -> Path:
        return self.config_path.parent / REALITY_KEYS_FILE

    def _load_reality_keys(self) -> None:
        path = self._keys_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._private_key = data.get("private_key", "")
            self._public_key = data.get("public_key", "")
            self._short_id = data.get("short_id", "")
            self._sni_domain = data.get("sni_domain", VLESS_REALITY_SNI)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load REALITY keys from %s", path)

    def _save_reality_keys(self) -> None:
        path = self._keys_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "private_key": self._private_key,
            "public_key": self._public_key,
            "short_id": self._short_id,
            "sni_domain": self._sni_domain,
        }
        path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(path, 0o600)
        except OSError:
            logger.warning("Failed to set permissions on %s", path)

    async def detect(self) -> ProtocolStatus:
        try:
            result = await run_command(
                ["systemctl", "is-active", self.service_name]
            )
            if result.success and result.stdout == "active":
                return ProtocolStatus.ACTIVE
            if not Path(XRAY_BINARY).exists():
                return ProtocolStatus.NOT_INSTALLED
            if not self.config_path.exists():
                return ProtocolStatus.NOT_INSTALLED
            return ProtocolStatus.DEGRADED
        except FileNotFoundError:
            return ProtocolStatus.NOT_INSTALLED

    async def install(
        self, listen_port: int, public_host: str
    ) -> InstallResult:
        if not 1 <= listen_port <= 65535:
            raise ValueError(f"Invalid port: {listen_port}")
        if not public_host:
            raise ValueError("public_host is required")

        self.public_host = public_host
        self._listen_port = listen_port

        if not Path(XRAY_BINARY).exists():
            await self._install_xray()

        if not self._public_key:
            await self._generate_reality_keys()

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_reality_config(listen_port)

        await self._write_systemd_unit()
        await run_command(
            ["sudo", VPNBOT_CTL, "service", "reload", "_"]
        )
        await run_command(
            ["sudo", VPNBOT_CTL, "service", "enable", self.service_name]
        )
        if not await self.reload_service():
            raise ServiceReloadError("Failed to start xray after install")

        await self._open_port(listen_port)

        return InstallResult(
            success=True,
            service_name=self.service_name,
            listen_port=listen_port,
            config_path=self.config_path,
        )

    async def create_client(
        self, external_name: str
    ) -> tuple[str, str]:
        if not external_name or not external_name.strip():
            raise ValueError("Client name cannot be empty")

        if not self.config_path.exists():
            if not self._private_key:
                if not Path(XRAY_BINARY).exists():
                    await self._install_xray()
                await self._generate_reality_keys()
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._create_reality_config(self._listen_port)

        await self.backup_config()

        config = load_config(self.config_path)
        credential = str(uuid.uuid4())
        updated_config = add_client_to_config(
            config, credential, external_name
        )
        save_config(self.config_path, updated_config)

        if not await self._validate_and_restart():
            raise ServiceReloadError(
                "Xray restart failed after client creation"
            )

        return credential, external_name

    async def delete_client(self, identifier: str) -> None:
        if not identifier or not identifier.strip():
            raise ValueError("Client identifier cannot be empty")

        if not self.config_path.exists():
            raise ServiceReloadError("Xray config not found")

        config = load_config(self.config_path)
        clients = get_clients_from_config(config)
        if not any(
            client.get("email") == identifier for client in clients
        ):
            raise ClientNotFoundError(identifier)

        await self.backup_config()

        updated_config = remove_client_from_config(config, identifier)
        save_config(self.config_path, updated_config)

        if not await self._validate_and_restart():
            raise ServiceReloadError(
                "Xray restart failed after client deletion"
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
            self.backups_dir / f"xray-config-{timestamp}.json"
        )
        shutil.copy2(self.config_path, backup_path)
        return str(backup_path)

    def generate_link(self, email: str) -> str:
        if not self._public_key:
            raise ServiceReloadError(
                "REALITY keys not loaded. Install VLESS first."
            )
        if not self.public_host:
            raise ServiceReloadError(
                "public_host not set. Install VLESS first."
            )
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

    async def collect_traffic(self) -> dict[str, dict[str, int]]:
        return {}

    async def _validate_and_restart(self) -> bool:
        validate_result = await run_command(
            [XRAY_BINARY, "test", "-config", str(self.config_path)],
            timeout=10.0,
        )
        if not validate_result.success:
            logger.error(
                "Xray config validation failed: %s",
                validate_result.stderr,
            )
            await self._rollback_config()
            return False

        restart_ok = await self.reload_service()
        if not restart_ok:
            logger.error("Xray restart failed, rolling back")
            await self._rollback_config()
            return False

        return True

    async def _rollback_config(self) -> None:
        if not self.backups_dir.exists():
            return
        backups = sorted(
            self.backups_dir.glob("xray-config-*.json"),
            reverse=True,
        )
        if not backups:
            return
        latest = backups[0]
        logger.warning("Rolling back Xray config from %s", latest)
        shutil.copy2(latest, self.config_path)
        await self.reload_service()

    async def _install_xray(self) -> None:
        logger.info("Installing Xray-core binary directly")

        arch_result = await run_command(["uname", "-m"], timeout=5.0)
        arch_map = {
            "x86_64": "64",
            "aarch64": "arm64-v8a",
            "armv7l": "arm32-v7a",
        }
        machine = arch_map.get(arch_result.stdout.strip(), "64")

        await run_command(
            ["sudo", VPNBOT_CTL, "file", "mkdir", str(XRAY_CONFIG_DIR)]
        )

        zip_url = (
            "https://github.com/XTLS/Xray-core/releases/"
            "latest/download/Xray-linux-{}.zip"
        ).format(machine)

        dl_result = await run_command(
            [
                "sudo", VPNBOT_CTL, "curl-dl", "download",
                zip_url, "/tmp/xray.zip",
            ],
            timeout=120.0,
        )
        if not dl_result.success:
            raise RuntimeError(
                f"Failed to download Xray: {dl_result.stderr}"
            )

        unzip_result = await run_command(
            ["sudo", "unzip", "-o", "/tmp/xray.zip",
             "-d", "/tmp/xray-extract"],
            timeout=30.0,
        )
        if not unzip_result.success:
            raise RuntimeError(
                f"Failed to extract Xray: {unzip_result.stderr}"
            )

        cp_result = await run_command(
            ["sudo", VPNBOT_CTL, "file", "cp",
             "/tmp/xray-extract/xray", XRAY_BINARY],
            timeout=10.0,
        )
        if not cp_result.success:
            raise RuntimeError(
                f"Failed to copy Xray binary: {cp_result.stderr}"
            )

        await run_command(
            ["sudo", VPNBOT_CTL, "file", "chmod", "755", XRAY_BINARY]
        )

        await run_command(
            ["sudo", "rm", "-rf", "/tmp/xray.zip", "/tmp/xray-extract"]
        )

    async def _generate_reality_keys(self) -> None:
        logger.info("Generating REALITY keys")
        result = await run_command([XRAY_BINARY, "x25519"])
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

        self._save_reality_keys()

    def _create_reality_config(self, listen_port: int) -> None:
        sni = self._sni_domain or VLESS_REALITY_SNI
        config = {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {
                    "port": listen_port,
                    "protocol": "vless",
                    "settings": {
                        "users": [],
                        "decryption": "none",
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "show": False,
                            "dest": f"{sni}:443",
                            "xver": 0,
                            "serverNames": [sni, f"www.{sni}"],
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
            ["sudo", VPNBOT_CTL, "file", "cp", tmp_path, XRAY_SERVICE]
        )

    async def _open_port(self, port: int) -> None:
        ufw_check = await run_command(["which", "ufw"])
        if ufw_check.success:
            await run_command(
                ["sudo", VPNBOT_CTL, "firewall", "allow", str(port)]
            )
