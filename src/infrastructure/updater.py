from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.infrastructure.shell_runner import run_command

logger = logging.getLogger(__name__)


class Updater:
    def __init__(
        self,
        app_dir: Path,
        backups_dir: Path,
        service_name: str = "vpnbot",
    ) -> None:
        self.app_dir = app_dir
        self.backups_dir = backups_dir
        self.service_name = service_name

    async def check_for_updates(self) -> bool:
        result = await run_command(
            ["git", "-C", str(self.app_dir), "fetch", "--dry-run"],
            cwd=str(self.app_dir),
        )
        return result.returncode == 0 and bool(result.stderr.strip())

    async def backup_before_update(self) -> str:
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup_path = self.backups_dir / f"pre-update-{timestamp}"
        shutil.copytree(self.app_dir, backup_path, dirs_exist_ok=True)
        logger.info("Backup created", extra={"path": str(backup_path)})
        return str(backup_path)

    async def apply_update(self) -> bool:
        backup_path = await self.backup_before_update()

        try:
            pull = await run_command(
                ["git", "-C", str(self.app_dir), "pull"],
                cwd=str(self.app_dir),
                timeout=120.0,
            )
            if not pull.success:
                logger.error("git pull failed", extra={"stderr": pull.stderr})
                await self._rollback(backup_path)
                return False

            install = await run_command(
                ["pip", "install", "-e", f"{self.app_dir}[dev]"],
                cwd=str(self.app_dir),
                timeout=120.0,
            )
            if not install.success:
                logger.error("pip install failed")
                await self._rollback(backup_path)
                return False

            restart = await run_command(
                ["systemctl", "restart", self.service_name],
            )
            if not restart.success:
                logger.error("restart failed")
                await self._rollback(backup_path)
                return False

            logger.info("Update applied successfully")
            return True

        except Exception:
            logger.exception("Update failed")
            await self._rollback(backup_path)
            return False

    async def _rollback(self, backup_path: str) -> None:
        logger.warning("Rolling back from %s", backup_path)
        try:
            shutil.copytree(backup_path, self.app_dir, dirs_exist_ok=True)
            await run_command(
                ["systemctl", "restart", self.service_name],
            )
            logger.info("Rollback completed")
        except Exception:
            logger.exception("Rollback failed")
