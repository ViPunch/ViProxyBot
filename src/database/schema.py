from __future__ import annotations

from typing import Sequence

import aiosqlite

SCHEMA_VERSION_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""

BASELINE_SQL = """
CREATE TABLE IF NOT EXISTS admins (
    telegram_user_id INTEGER PRIMARY KEY,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS protocol_installations (
    protocol TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    listen_port INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    config_path TEXT NOT NULL,
    installed_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol TEXT NOT NULL,
    external_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE(protocol, external_name)
);

CREATE TABLE IF NOT EXISTS client_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    protocol TEXT NOT NULL,
    uuid TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS traffic_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol TEXT NOT NULL,
    client_id INTEGER,
    rx_bytes INTEGER NOT NULL,
    tx_bytes INTEGER NOT NULL,
    collected_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_telegram_user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL,
    details_redacted TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clients_protocol_status
    ON clients(protocol, status);

CREATE INDEX IF NOT EXISTS idx_traffic_snapshots_client_collected_at
    ON traffic_snapshots(client_id, collected_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_actor_created_at
    ON audit_events(actor_telegram_user_id, created_at);
"""

MIGRATIONS: Sequence[tuple[int, str, str]] = [
    (1, "baseline", BASELINE_SQL),
]


async def _get_current_version(conn: aiosqlite.Connection) -> int:
    try:
        cursor = await conn.execute(
            "SELECT MAX(version) FROM schema_version"
        )
        row = await cursor.fetchone()
        if row is None or row[0] is None:
            return 0
        return int(row[0])
    except Exception:
        return 0


async def apply_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA_VERSION_SQL)
    await conn.commit()

    current = await _get_current_version(conn)

    for version, name, sql in MIGRATIONS:
        if version <= current:
            continue
        await conn.executescript(sql)
        await conn.execute(
            "INSERT INTO schema_version (version, name, applied_at) "
            "VALUES (?, ?, datetime('now'))",
            (version, name),
        )
        await conn.commit()


SCHEMA_SQL = BASELINE_SQL
