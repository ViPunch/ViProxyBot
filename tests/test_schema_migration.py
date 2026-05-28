import aiosqlite
import pytest

from src.database.schema import (
    BASELINE_SQL,
    MIGRATIONS,
    SCHEMA_VERSION_SQL,
    _get_current_version,
    apply_schema,
)


@pytest.fixture
async def in_memory_db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    yield conn
    await conn.close()


class TestSchemaVersion:
    async def test_version_table_created(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await in_memory_db.executescript(SCHEMA_VERSION_SQL)
        await in_memory_db.commit()
        cursor = await in_memory_db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='schema_version'"
        )
        assert await cursor.fetchone() is not None

    async def test_initial_version_is_zero(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await in_memory_db.executescript(SCHEMA_VERSION_SQL)
        await in_memory_db.commit()
        version = await _get_current_version(in_memory_db)
        assert version == 0


class TestApplySchema:
    async def test_baseline_creates_all_tables(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await apply_schema(in_memory_db)
        cursor = await in_memory_db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        expected = {
            "admins",
            "audit_events",
            "client_credentials",
            "clients",
            "protocol_installations",
            "schema_version",
            "traffic_snapshots",
        }
        assert set(tables) == expected

    async def test_baseline_creates_indexes(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await apply_schema(in_memory_db)
        cursor = await in_memory_db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        assert "idx_clients_protocol_status" in indexes
        assert "idx_traffic_snapshots_client_collected_at" in indexes
        assert "idx_audit_events_actor_created_at" in indexes

    async def test_version_set_to_1_after_baseline(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await apply_schema(in_memory_db)
        version = await _get_current_version(in_memory_db)
        assert version == 1

    async def test_idempotent(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await apply_schema(in_memory_db)
        await apply_schema(in_memory_db)
        version = await _get_current_version(in_memory_db)
        assert version == 1

    async def test_schema_version_recorded(
        self, in_memory_db: aiosqlite.Connection
    ) -> None:
        await apply_schema(in_memory_db)
        cursor = await in_memory_db.execute(
            "SELECT version, name FROM schema_version "
            "ORDER BY version"
        )
        rows = await cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "baseline"


class TestMigrationDefinitions:
    def test_migrations_sorted_by_version(self) -> None:
        versions = [m[0] for m in MIGRATIONS]
        assert versions == sorted(versions)

    def test_baseline_sql_not_empty(self) -> None:
        assert len(BASELINE_SQL.strip()) > 0
