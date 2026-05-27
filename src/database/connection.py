from __future__ import annotations

from pathlib import Path

import aiosqlite

_DB_PATH = Path("data/vpnbot.db")


def set_db_path(path: Path) -> None:
    global _DB_PATH
    _DB_PATH = Path(path)


async def get_connection() -> aiosqlite.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(_DB_PATH)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA journal_mode=WAL;")
    await connection.execute("PRAGMA foreign_keys = ON;")
    return connection
