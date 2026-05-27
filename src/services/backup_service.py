from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(
        self,
        registry: ProtocolRegistry,
        backups_dir: Path,
        db_path: Path,
    ) -> None:
        self.registry = registry
        self.backups_dir = backups_dir
        self.db_path = db_path

    async def backup_all(self) -> list[str]:
        artifacts: list[str] = []
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        db_backup = self.backups_dir / f"vpnbot-{timestamp}.db"
        try:
            shutil.copy2(self.db_path, db_backup)
            artifacts.append(str(db_backup))
        except Exception:
            logger.exception("Database backup failed")

        for protocol in self.registry.list_registered():
            adapter = self.registry.get(protocol)
            if adapter is None:
                continue
            try:
                result = await adapter.backup_config()
                if result:
                    artifacts.append(result)
            except Exception:
                logger.exception(
                    "Config backup failed",
                    extra={"protocol": protocol.value},
                )

        return artifacts
