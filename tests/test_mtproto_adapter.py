import json
from pathlib import Path

import pytest

from src.infrastructure.protocols.mtproto.adapter import (
    SECRETS_FILE,
    MtprotoAdapter,
)
from src.infrastructure.protocols.mtproto.link_generator import (
    generate_mtproto_link,
    generate_mtproto_tg_link,
)


class TestLinkGenerator:
    def test_generate_link(self) -> None:
        link = generate_mtproto_link("1.2.3.4", 8443, "abc123")
        assert "t.me/proxy?server=1.2.3.4&port=8443&secret=abc123" in link

    def test_generate_tg_link(self) -> None:
        link = generate_mtproto_tg_link("1.2.3.4", 8443, "abc123")
        assert "tg://proxy?server=1.2.3.4&port=8443&secret=abc123" in link


class TestSecretPersistence:
    def test_save_and_load_secrets(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        adapter._secrets = {"alice": "secret-a", "bob": "secret-b"}
        adapter._proxy_tag = "test-tag"
        adapter._save_secrets()

        assert (config_dir / SECRETS_FILE).exists()
        data = json.loads((config_dir / SECRETS_FILE).read_text())
        assert data["secrets"]["alice"] == "secret-a"
        assert data["proxy_tag"] == "test-tag"

    def test_load_secrets_on_init(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        data = {
            "secrets": {"user1": "sec1", "user2": "sec2"},
            "proxy_tag": "tag123",
        }
        (config_dir / SECRETS_FILE).write_text(json.dumps(data))

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        assert adapter._secrets == {"user1": "sec1", "user2": "sec2"}
        assert adapter._proxy_tag == "tag123"

    def test_load_secrets_missing_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        assert adapter._secrets == {}

    def test_load_secrets_corrupted(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()
        (config_dir / SECRETS_FILE).write_text("not json")

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        assert adapter._secrets == {}


class TestAdapterLifecycle:
    def test_generate_link_from_secret(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        adapter._secrets = {"test": "my-secret"}
        adapter._listen_port = 8443

        link = adapter.generate_link("test")
        assert "t.me/proxy" in link
        assert "my-secret" in link
        assert "1.2.3.4" in link
        assert "8443" in link

    def test_generate_link_from_file(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()
        (config_dir / "mtproxy.secret").write_text("file-secret")

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        adapter._listen_port = 8443

        link = adapter.generate_link("test")
        assert "file-secret" in link

    def test_generate_link_raises_without_secret(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        with pytest.raises(Exception):
            adapter.generate_link("test")

    def test_generate_tg_link(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        adapter._secrets = {"test": "sec"}
        adapter._listen_port = 8443

        link = adapter.generate_tg_link("test")
        assert "tg://proxy" in link

    def test_get_primary_secret(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        adapter._secrets = {"a": "sec-a", "b": "sec-b"}
        primary = adapter._get_primary_secret()
        assert primary in ("sec-a", "sec-b")

    def test_get_primary_secret_empty(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        assert adapter._get_primary_secret() == ""

    def test_backup_creates_dir(self, tmp_path: Path) -> None:
        import asyncio

        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()
        (config_dir / "mtproxy.secret").write_text("test")

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        result = asyncio.run(adapter.backup_config())
        assert result is not None
        assert Path(result).exists()
        assert "mtproto-config-" in Path(result).name

    def test_backup_returns_none_if_no_dir(self, tmp_path: Path) -> None:
        import asyncio

        adapter = MtprotoAdapter(
            tmp_path / "nonexistent", tmp_path / "backups", "1.2.3.4"
        )
        result = asyncio.run(adapter.backup_config())
        assert result is None

    def test_collect_traffic_returns_empty(self, tmp_path: Path) -> None:
        import asyncio

        config_dir = tmp_path / "mtproto"
        config_dir.mkdir()

        adapter = MtprotoAdapter(config_dir, tmp_path / "backups", "1.2.3.4")
        result = asyncio.run(adapter.collect_traffic())
        assert result == {}
