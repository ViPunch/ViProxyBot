from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.services.protocol_registry import ProtocolRegistry

logger = logging.getLogger(__name__)

MAX_BACKUPS = 10


class BackupService:
    def __init__(
        self,
        registry: ProtocolRegistry,
        backups_dir: Path,
        db_path: Path,
        max_backups: int = MAX_BACKUPS,
    ) -> None:
        self.registry = registry
        self.backups_dir = backups_dir
        self.db_path = db_path
        self.max_backups = max_backups

    async def backup_all(self) -> list[str]:
        artifacts: list[str] = []
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        db_backup = self.backups_dir / f"vpnbot-{timestamp}.db"
        try:
            self._backup_database(db_backup)
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

        self._rotate_backups()
        return artifacts

    def _backup_database(self, dest: Path) -> None:
        if not self.db_path.exists():
            return
        source = sqlite3.connect(str(self.db_path))
        dest_conn = sqlite3.connect(str(dest))
        try:
            source.backup(dest_conn)
        finally:
            dest_conn.close()
            source.close()

    def _rotate_backups(self) -> None:
        db_backups = sorted(
            self.backups_dir.glob("vpnbot-*.db"),
            reverse=True,
        )
        for old in db_backups[self.max_backups :]:
            try:
                old.unlink()
                logger.info("Rotated old backup: %s", old.name)
            except OSError:
                logger.warning("Failed to remove old backup: %s", old.name)
