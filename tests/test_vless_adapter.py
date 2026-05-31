import json
from pathlib import Path

import pytest

from src.infrastructure.protocols.vless.adapter import (
    REALITY_KEYS_FILE,
    VlessAdapter,
)
from src.infrastructure.protocols.vless.config_writer import (
    add_client_to_config,
    get_clients_from_config,
    get_listen_port_from_config,
    load_config,
    remove_client_from_config,
    save_config,
)


def _make_xray_config(
    listen_port: int = 443,
    clients: list[dict] | None = None,
) -> dict:
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": listen_port,
                "protocol": "vless",
                "settings": {
                    "clients": clients or [],
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "privateKey": "test-priv",
                        "shortIds": ["abc123"],
                    },
                },
            }
        ],
        "outbounds": [{"protocol": "freedom"}],
    }


class TestConfigWriter:
    def test_add_client(self, tmp_path: Path) -> None:
        config = _make_xray_config()
        updated = add_client_to_config(config, "uuid-1", "alice")
        clients = get_clients_from_config(updated)
        assert len(clients) == 1
        assert clients[0]["id"] == "uuid-1"
        assert clients[0]["email"] == "alice"
        assert clients[0]["flow"] == "xtls-rprx-vision"

    def test_add_multiple_clients(self, tmp_path: Path) -> None:
        config = _make_xray_config()
        config = add_client_to_config(config, "uuid-1", "alice")
        config = add_client_to_config(config, "uuid-2", "bob")
        clients = get_clients_from_config(config)
        assert len(clients) == 2

    def test_add_duplicate_client_raises(self, tmp_path: Path) -> None:
        config = _make_xray_config()
        config = add_client_to_config(config, "uuid-1", "alice")
        with pytest.raises(ValueError, match="already exists"):
            add_client_to_config(config, "uuid-2", "alice")

    def test_remove_client(self, tmp_path: Path) -> None:
        config = _make_xray_config()
        config = add_client_to_config(config, "uuid-1", "alice")
        config = add_client_to_config(config, "uuid-2", "bob")
        config = remove_client_from_config(config, "alice")
        clients = get_clients_from_config(config)
        assert len(clients) == 1
        assert clients[0]["email"] == "bob"

    def test_remove_nonexistent_client(self, tmp_path: Path) -> None:
        config = _make_xray_config()
        config = add_client_to_config(config, "uuid-1", "alice")
        config = remove_client_from_config(config, "unknown")
        clients = get_clients_from_config(config)
        assert len(clients) == 1

    def test_save_and_load(self, tmp_path: Path) -> None:
        config = _make_xray_config(listen_port=8443)
        path = tmp_path / "config.json"
        save_config(path, config)
        loaded = load_config(path)
        assert get_listen_port_from_config(loaded) == 8443

    def test_get_listen_port(self) -> None:
        config = _make_xray_config(listen_port=443)
        assert get_listen_port_from_config(config) == 443


class TestRealityKeyPersistence:
    def test_save_and_load_keys(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        adapter._private_key = "priv-test"
        adapter._public_key = "pub-test"
        adapter._short_id = "sid-test"
        adapter._sni_domain = "example.com"
        adapter._save_reality_keys()

        keys_file = tmp_path / REALITY_KEYS_FILE
        assert keys_file.exists()
        data = json.loads(keys_file.read_text())
        assert data["private_key"] == "priv-test"
        assert data["public_key"] == "pub-test"

    def test_load_keys_on_init(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        keys_data = {
            "private_key": "loaded-priv",
            "public_key": "loaded-pub",
            "short_id": "loaded-sid",
            "sni_domain": "loaded.com",
        }
        keys_file = tmp_path / REALITY_KEYS_FILE
        keys_file.write_text(json.dumps(keys_data))

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        assert adapter._private_key == "loaded-priv"
        assert adapter._public_key == "loaded-pub"
        assert adapter._short_id == "loaded-sid"
        assert adapter._sni_domain == "loaded.com"

    def test_load_keys_missing_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        assert adapter._private_key == ""
        assert adapter._public_key == ""

    def test_load_keys_corrupted_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        keys_file = tmp_path / REALITY_KEYS_FILE
        keys_file.write_text("not json")

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        assert adapter._private_key == ""


class TestLinkGeneration:
    def test_generate_link_from_persisted_keys(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.json"
        config = _make_xray_config(
            clients=[{"id": "uuid-1", "email": "alice", "flow": "xtls-rprx-vision"}]
        )
        config["inbounds"][0]["streamSettings"]["realitySettings"][
            "fingerprint"
        ] = "firefox"
        save_config(config_path, config)

        keys_data = {
            "private_key": "priv",
            "public_key": "pub-key-123",
            "short_id": "sid-456",
            "sni_domain": "www.microsoft.com",
        }
        (tmp_path / REALITY_KEYS_FILE).write_text(
            json.dumps(keys_data)
        )

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        link = adapter.generate_link("alice")
        assert link.startswith("vless://uuid-1@1.2.3.4:443")
        assert "pbk=pub-key-123" in link
        assert "sid=sid-456" in link
        assert "sni=www.microsoft.com" in link
        assert "fp=firefox" in link

    def test_generate_link_raises_for_missing_client(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        keys_data = {
            "private_key": "priv",
            "public_key": "pub",
            "short_id": "sid",
            "sni_domain": "sni",
        }
        (tmp_path / REALITY_KEYS_FILE).write_text(
            json.dumps(keys_data)
        )

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(Exception):
            adapter.generate_link("nonexistent")

    def test_generate_link_raises_without_keys(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(Exception):
            adapter.generate_link("alice")


class TestBackup:
    def test_backup_creates_file(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())
        backups_dir = tmp_path / "backups"

        import asyncio

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=backups_dir,
            public_host="1.2.3.4",
        )
        result = asyncio.run(adapter.backup_config())
        assert result is not None
        assert Path(result).exists()
        assert "xray-config-" in Path(result).name

    def test_backup_returns_none_if_no_config(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        adapter = VlessAdapter(
            config_path=tmp_path / "nonexistent.json",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        result = asyncio.run(adapter.backup_config())
        assert result is None


class TestCreateClientAutoKeyGeneration:
    def test_creates_keys_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        config_path = tmp_path / "config.json"
        backups_dir = tmp_path / "backups"

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=backups_dir,
            public_host="1.2.3.4",
        )
        assert adapter._private_key == ""
        assert not config_path.exists()

        async def mock_install_xray(self_adapter: VlessAdapter) -> None:
            pass

        async def mock_generate_keys(self_adapter: VlessAdapter) -> None:
            self_adapter._private_key = "auto-priv"
            self_adapter._public_key = "auto-pub"
            self_adapter._short_id = "auto-sid"
            self_adapter._save_reality_keys()

        async def mock_validate(self_adapter: VlessAdapter) -> bool:
            return True

        async def mock_backup(self_adapter: VlessAdapter) -> str | None:
            return None

        monkeypatch.setattr(
            VlessAdapter, "_install_xray", mock_install_xray
        )
        monkeypatch.setattr(
            VlessAdapter, "_generate_reality_keys", mock_generate_keys
        )
        monkeypatch.setattr(
            VlessAdapter, "_validate_and_restart", mock_validate
        )
        monkeypatch.setattr(
            VlessAdapter, "backup_config", mock_backup
        )

        credential, name = asyncio.run(
            adapter.create_client("test-user")
        )
        assert name == "test-user"
        assert len(credential) > 0
        assert config_path.exists()
        assert adapter._private_key == "auto-priv"


class TestValidation:
    def test_create_client_empty_name_raises(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(ValueError, match="cannot be empty"):
            asyncio.run(adapter.create_client(""))

    def test_create_client_whitespace_name_raises(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(ValueError, match="cannot be empty"):
            asyncio.run(adapter.create_client("   "))

    def test_delete_client_empty_identifier_raises(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        config_path = tmp_path / "config.json"
        save_config(config_path, _make_xray_config())

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(ValueError, match="cannot be empty"):
            asyncio.run(adapter.delete_client(""))

    def test_create_inbound_invalid_port_raises(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        from src.infrastructure.protocols.vless.adapter import InboundConfig

        adapter = VlessAdapter(
            config_path=tmp_path / "config.json",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        config = InboundConfig(port=0)
        with pytest.raises(ValueError, match="Invalid port"):
            asyncio.run(adapter.create_inbound(config))

    def test_create_inbound_port_too_high_raises(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        from src.infrastructure.protocols.vless.adapter import InboundConfig

        adapter = VlessAdapter(
            config_path=tmp_path / "config.json",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        config = InboundConfig(port=99999)
        with pytest.raises(ValueError, match="Invalid port"):
            asyncio.run(adapter.create_inbound(config))

    def test_install_base_empty_host_raises(self, tmp_path: Path) -> None:
        import asyncio

        adapter = VlessAdapter(
            config_path=tmp_path / "config.json",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(ValueError, match="public_host is required"):
            asyncio.run(adapter.install_base(""))


class TestGenerateRealityKeys:
    def test_parse_x25519_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        from src.infrastructure.shell_runner import ShellResult

        config_path = tmp_path / "config.json"

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )

        mock_result = ShellResult(
            returncode=0,
            stdout=(
                "PrivateKey: test-priv-key-123\n"
                "Password (PublicKey): test-pub-key-456"
            ),
            stderr="",
            success=True,
        )

        async def mock_run_command(*args, **kwargs):
            return mock_result

        monkeypatch.setattr(
            "src.infrastructure.protocols.vless.adapter.run_command",
            mock_run_command,
        )

        async def run_test():
            await adapter._generate_reality_keys()

        asyncio.run(run_test())
        assert adapter._private_key == "test-priv-key-123"
        assert adapter._public_key == "test-pub-key-456"
        assert len(adapter._short_id) == 16

    def test_parse_x25519_output_old_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        from src.infrastructure.shell_runner import ShellResult

        config_path = tmp_path / "config.json"

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )

        mock_result = ShellResult(
            returncode=0,
            stdout="Private key: old-format-priv\nPublic key: old-format-pub",
            stderr="",
            success=True,
        )

        async def mock_run_command(*args, **kwargs):
            return mock_result

        monkeypatch.setattr(
            "src.infrastructure.protocols.vless.adapter.run_command",
            mock_run_command,
        )

        async def run_test():
            await adapter._generate_reality_keys()

        asyncio.run(run_test())
        assert adapter._private_key == "old-format-priv"
        assert adapter._public_key == "old-format-pub"

    def test_parse_x25519_output_raises_on_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        from src.infrastructure.shell_runner import ShellResult

        config_path = tmp_path / "config.json"

        adapter = VlessAdapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )

        mock_result = ShellResult(
            returncode=0,
            stdout="some garbage output",
            stderr="",
            success=True,
        )

        async def mock_run_command(*args, **kwargs):
            return mock_result

        monkeypatch.setattr(
            "src.infrastructure.protocols.vless.adapter.run_command",
            mock_run_command,
        )

        async def run_test():
            await adapter._generate_reality_keys()

        with pytest.raises(RuntimeError, match="Failed to parse REALITY keys"):
            asyncio.run(run_test())
