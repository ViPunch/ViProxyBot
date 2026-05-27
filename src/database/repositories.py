from __future__ import annotations

from datetime import datetime
from typing import cast

import aiosqlite

from src.domain.enums import ClientStatus, ProtocolType
from src.domain.models import (
    AuditEvent,
    ClientAccount,
    ClientCredential,
    ProtocolInstallation,
)


class AdminRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def upsert_admin(
        self,
        telegram_user_id: int,
        *,
        is_active: bool = True,
        last_seen_at: datetime | None = None,
    ) -> None:
        created_at = datetime.utcnow().isoformat()
        await self.conn.execute(
            """
            INSERT INTO admins (telegram_user_id, is_active, created_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                is_active = excluded.is_active,
                last_seen_at = excluded.last_seen_at
            """,
            (
                telegram_user_id,
                int(is_active),
                created_at,
                last_seen_at.isoformat() if last_seen_at else None,
            ),
        )
        await self.conn.commit()

    async def is_admin(self, telegram_user_id: int) -> bool:
        cursor = await self.conn.execute(
            "SELECT is_active FROM admins WHERE telegram_user_id = ?",
            (telegram_user_id,),
        )
        row = await cursor.fetchone()
        return bool(row[0]) if row else False

    async def list_admins(self) -> list[int]:
        cursor = await self.conn.execute(
            "SELECT telegram_user_id FROM admins "
            "WHERE is_active = 1 ORDER BY telegram_user_id"
        )
        rows = await cursor.fetchall()
        return [int(row[0]) for row in rows]


class ProtocolRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def upsert_installation(self, installation: ProtocolInstallation) -> None:
        installed_at = (
            installation.installed_at.isoformat()
            if installation.installed_at
            else None
        )
        updated_at = (
            installation.updated_at.isoformat()
            if installation.updated_at
            else None
        )
        await self.conn.execute(
            """
            INSERT INTO protocol_installations (
                protocol,
                status,
                listen_port,
                service_name,
                config_path,
                installed_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(protocol) DO UPDATE SET
                status = excluded.status,
                listen_port = excluded.listen_port,
                service_name = excluded.service_name,
                config_path = excluded.config_path,
                installed_at = excluded.installed_at,
                updated_at = excluded.updated_at
            """,
            (
                installation.protocol.value,
                installation.status.value,
                installation.listen_port,
                installation.service_name,
                str(installation.config_path),
                installed_at,
                updated_at,
            ),
        )
        await self.conn.commit()

    async def get_installation(
        self,
        protocol: ProtocolType,
    ) -> ProtocolInstallation | None:
        cursor = await self.conn.execute(
            """
            SELECT
                protocol,
                status,
                listen_port,
                service_name,
                config_path,
                installed_at,
                updated_at
            FROM protocol_installations
            WHERE protocol = ?
            """,
            (protocol.value,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        installed_at = (
            datetime.fromisoformat(row["installed_at"])
            if row["installed_at"]
            else None
        )
        updated_at = (
            datetime.fromisoformat(row["updated_at"])
            if row["updated_at"]
            else None
        )
        return ProtocolInstallation(
            protocol=ProtocolType(row["protocol"]),
            status=row["status"],
            listen_port=row["listen_port"],
            service_name=row["service_name"],
            config_path=row["config_path"],
            installed_at=installed_at,
            updated_at=updated_at,
        )


class ClientRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def create_client(
        self,
        protocol: ProtocolType,
        external_name: str,
        uuid: str,
        *,
        created_at: datetime | None = None,
    ) -> ClientAccount:
        created_at = created_at or datetime.utcnow()
        cursor = await self.conn.execute(
            """
            INSERT INTO clients (
                protocol,
                external_name,
                status,
                created_at,
                revoked_at
            )
            VALUES (?, ?, ?, ?, NULL)
            """,
            (
                protocol.value,
                external_name,
                ClientStatus.ACTIVE.value,
                created_at.isoformat(),
            ),
        )
        client_id = cast(int, cursor.lastrowid)
        await self.conn.execute(
            """
            INSERT INTO client_credentials (client_id, protocol, uuid, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (client_id, protocol.value, uuid, created_at.isoformat()),
        )
        await self.conn.commit()
        return ClientAccount(
            id=int(client_id),
            protocol=protocol,
            external_name=external_name,
            status=ClientStatus.ACTIVE,
            created_at=created_at,
        )


class TrafficRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def save_snapshot(
        self,
        protocol: ProtocolType,
        client_name: str,
        rx_bytes: int,
        tx_bytes: int,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO traffic_snapshots (
                protocol, client_id, rx_bytes, tx_bytes, collected_at
            )
            VALUES (?, NULL, ?, ?, ?)
            """,
            (
                protocol.value,
                rx_bytes,
                tx_bytes,
                datetime.utcnow().isoformat(),
            ),
        )
        await self.conn.commit()

    async def get_latest_snapshots(
        self,
        protocol: ProtocolType,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        cursor = await self.conn.execute(
            """
            SELECT protocol, client_id, rx_bytes, tx_bytes, collected_at
            FROM traffic_snapshots
            WHERE protocol = ?
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (protocol.value, limit),
        )
        rows = await cursor.fetchall()
        return [
            {
                "protocol": row["protocol"],
                "client_id": row["client_id"],
                "rx_bytes": row["rx_bytes"],
                "tx_bytes": row["tx_bytes"],
                "collected_at": row["collected_at"],
            }
            for row in rows
        ]

        row = await cursor.fetchone()
        if row is None:
            return None
        return ClientAccount(
            id=row["id"],
            protocol=ProtocolType(row["protocol"]),
            external_name=row["external_name"],
            status=ClientStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def get_credential(self, client_id: int) -> ClientCredential | None:
        cursor = await self.conn.execute(
            "SELECT id, client_id, protocol, uuid, created_at "
            "FROM client_credentials WHERE client_id = ?",
            (client_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ClientCredential(
            id=row["id"],
            client_id=row["client_id"],
            protocol=ProtocolType(row["protocol"]),
            uuid=row["uuid"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def list_clients(self, protocol: ProtocolType) -> list[ClientAccount]:
        cursor = await self.conn.execute(
            """
            SELECT id, protocol, external_name, status, created_at
            FROM clients
            WHERE protocol = ?
            ORDER BY created_at ASC
            """,
            (protocol.value,),
        )
        rows = await cursor.fetchall()
        return [
            ClientAccount(
                id=row["id"],
                protocol=ProtocolType(row["protocol"]),
                external_name=row["external_name"],
                status=ClientStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    async def revoke_client(self, client_id: int) -> None:
        await self.conn.execute(
            "UPDATE clients SET status = ?, revoked_at = ? WHERE id = ?",
            (ClientStatus.REVOKED.value, datetime.utcnow().isoformat(), client_id),
        )
        await self.conn.commit()

    async def get_client_by_name(
        self,
        protocol: ProtocolType,
        external_name: str,
    ) -> ClientAccount | None:
        cursor = await self.conn.execute(
            """
            SELECT id, protocol, external_name, status, created_at
            FROM clients
            WHERE protocol = ? AND external_name = ?
            """,
            (protocol.value, external_name),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ClientAccount(
            id=row["id"],
            protocol=ProtocolType(row["protocol"]),
            external_name=row["external_name"],
            status=ClientStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class AuditRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def log(
        self,
        actor_telegram_user_id: int,
        action: str,
        target_type: str,
        target_id: str,
        status: str,
        details_redacted: str,
        *,
        created_at: datetime | None = None,
    ) -> AuditEvent:
        created_at = created_at or datetime.utcnow()
        cursor = await self.conn.execute(
            """
            INSERT INTO audit_events (
                actor_telegram_user_id,
                action,
                target_type,
                target_id,
                status,
                details_redacted,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor_telegram_user_id,
                action,
                target_type,
                target_id,
                status,
                details_redacted,
                created_at.isoformat(),
            ),
        )
        await self.conn.commit()
        event_id = cast(int, cursor.lastrowid)
        return AuditEvent(
            id=event_id,
            actor_telegram_user_id=actor_telegram_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            details_redacted=details_redacted,
            created_at=created_at,
        )
