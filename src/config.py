from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    bot_token: str
    admin_ids: list[int]
    encryption_key: str
    vps_public_ip: str
    db_path: Path = Field(default=Path("data/vpnbot.db"))
    backups_dir: Path = Field(default=Path("data/backups"))
    xray_config_dir: Path = Field(default=Path("data/xray"))
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
            db_path=Path(os.environ.get("DB_PATH", "data/vpnbot.db")),
            backups_dir=Path(os.environ.get("BACKUPS_DIR", "data/backups")),
            xray_config_dir=Path(
                os.environ.get("XRAY_CONFIG_DIR", "data/xray")
            ),
        )
