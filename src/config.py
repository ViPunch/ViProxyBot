from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    bot_token: str
    admin_ids: list[int]
    encryption_key: str
    vps_public_ip: str

    public_host: str = Field(
        default="",
        description="Domain name or IP for certificate issuance and access links",
    )
    ssl_mode: str = Field(
        default="skip",
        description="SSL mode: domain, custom, or skip",
    )
    ssl_cert_path: Path = Field(
        default=Path("/etc/vpnbot/certs/selfsigned/cert.pem"),
    )
    ssl_key_path: Path = Field(
        default=Path("/etc/vpnbot/certs/selfsigned/key.pem"),
    )
    domain: str = Field(
        default="",
        description="Domain for Let's Encrypt certificate (ssl_mode=domain)",
    )

    db_path: Path = Field(default=Path("/opt/vpnbot/data/vpnbot.db"))
    backups_dir: Path = Field(default=Path("/opt/vpnbot/data/backups"))
    xray_config_dir: Path = Field(default=Path("/opt/vpnbot/data/xray"))
    hysteria_config_dir: Path = Field(
        default=Path("/opt/vpnbot/data/hysteria2")
    )
    rate_limit_commands: int = Field(default=30)
    rate_limit_heavy_ops: int = Field(default=5)
    rate_limit_window: int = Field(default=60)
    alert_chat_ids: list[int] = Field(default_factory=list)
    auto_update_enabled: bool = Field(default=False)
    auto_update_check_interval: int = Field(default=3600)

    @classmethod
    def from_env(cls) -> "AppConfig":
        admin_ids_raw = os.environ.get("ADMIN_IDS", "")
        admin_ids = [
            int(admin_id.strip())
            for admin_id in admin_ids_raw.split(",")
            if admin_id.strip()
        ]

        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            admin_ids=admin_ids,
            encryption_key=os.environ["ENCRYPTION_KEY"],
            vps_public_ip=os.environ["VPS_PUBLIC_IP"],
            public_host=os.environ.get("PUBLIC_HOST", ""),
            ssl_mode=os.environ.get("SSL_MODE", "skip"),
            ssl_cert_path=Path(
                os.environ.get(
                    "SSL_CERT_PATH",
                    "/etc/vpnbot/certs/selfsigned/cert.pem",
                )
            ),
            ssl_key_path=Path(
                os.environ.get(
                    "SSL_KEY_PATH",
                    "/etc/vpnbot/certs/selfsigned/key.pem",
                )
            ),
            domain=os.environ.get("DOMAIN", ""),
            db_path=Path(
                os.environ.get("DB_PATH", "/opt/vpnbot/data/vpnbot.db")
            ),
            backups_dir=Path(
                os.environ.get("BACKUPS_DIR", "/opt/vpnbot/data/backups")
            ),
            xray_config_dir=Path(
                os.environ.get(
                    "XRAY_CONFIG_DIR", "/opt/vpnbot/data/xray"
                )
            ),
            hysteria_config_dir=Path(
                os.environ.get(
                    "HYSTERIA_CONFIG_DIR", "/opt/vpnbot/data/hysteria2"
                )
            ),
        )

    @property
    def effective_host(self) -> str:
        return self.public_host or self.vps_public_ip

    @property
    def ssl_enabled(self) -> bool:
        return self.ssl_mode != "skip"
