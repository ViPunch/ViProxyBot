from pathlib import Path

import pytest
import yaml

from src.infrastructure.protocols.hysteria2.adapter import Hysteria2Adapter
from src.infrastructure.protocols.hysteria2.config_writer import (
    create_server_config,
    get_auth_password,
    get_listen_port,
    get_stats_endpoint,
    get_stats_secret,
    load_config,
    save_config,
    update_auth_password,
)


def _make_hysteria_config(
    listen_port: int = 443,
    password: str = "test-pass",
) -> dict:
    return {
        "listen": f":{listen_port}",
        "tls": {"cert": "/etc/hysteria/cert.pem", "key": "/etc/hysteria/key.pem"},
        "auth": {"type": "password", "password": password},
        "trafficStats": {
            "listen": "127.0.0.1:25199",
            "secret": "stats-secret",
        },
    }


class TestConfigWriter:
    def test_create_server_config(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        create_server_config(
            path,
            listen_port=443,
            cert_path="/etc/cert.pem",
            key_path="/etc/key.pem",
            auth_password="mypass",
        )
        assert path.exists()
        config = load_config(path)
        assert get_listen_port(config) == 443
        assert get_auth_password(config) == "mypass"

    def test_load_save_roundtrip(self, tmp_path: Path) -> None:
        config = _make_hysteria_config(listen_port=8443)
        path = tmp_path / "config.yaml"
        save_config(path, config)
        loaded = load_config(path)
        assert get_listen_port(loaded) == 8443

    def test_get_auth_password(self) -> None:
        config = _make_hysteria_config(password="secret123")
        assert get_auth_password(config) == "secret123"

    def test_get_listen_port_string(self) -> None:
        config = {"listen": ":8443"}
        assert get_listen_port(config) == 8443

    def test_get_listen_port_int(self) -> None:
        config = {"listen": 8443}
        assert get_listen_port(config) == 8443

    def test_update_auth_password(self) -> None:
        config = _make_hysteria_config(password="old")
        updated = update_auth_password(config, "new")
        assert get_auth_password(updated) == "new"
        assert get_auth_password(config) == "old"

    def test_get_stats_endpoint(self) -> None:
        config = _make_hysteria_config()
        assert get_stats_endpoint(config) == "http://127.0.0.1:25199"

    def test_get_stats_endpoint_missing(self) -> None:
        config = {"listen": ":443"}
        assert get_stats_endpoint(config) is None

    def test_get_stats_secret(self) -> None:
        config = _make_hysteria_config()
        assert get_stats_secret(config) == "stats-secret"


class TestAdapterLifecycle:
    def test_generate_link(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config = _make_hysteria_config(password="link-pass")
        save_config(config_path, config)

        adapter = Hysteria2Adapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        link = adapter.generate_link("test")
        assert "hysteria2://link-pass@1.2.3.4:443" in link
        assert "#test" in link

    def test_generate_link_with_insecure(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        save_config(config_path, _make_hysteria_config())

        adapter = Hysteria2Adapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
            cert_path="",
            key_path="",
        )
        link = adapter.generate_link("test")
        assert "insecure=1" in link

    def test_generate_link_no_insecure_with_cert(
        self, tmp_path: Path
    ) -> None:
        config_path = tmp_path / "config.yaml"
        save_config(config_path, _make_hysteria_config())

        adapter = Hysteria2Adapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
            cert_path="/some/cert.pem",
            key_path="/some/key.pem",
        )
        link = adapter.generate_link("test")
        assert "insecure" not in link

    def test_generate_link_raises_without_config(
        self, tmp_path: Path
    ) -> None:
        adapter = Hysteria2Adapter(
            config_path=tmp_path / "nonexistent.yaml",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        with pytest.raises(Exception):
            adapter.generate_link("test")

    def test_generate_client_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        save_config(config_path, _make_hysteria_config(password="cfg-pass"))

        adapter = Hysteria2Adapter(
            config_path=config_path,
            backups_dir=tmp_path / "backups",
            public_host="example.com",
        )
        text = adapter.generate_client_config("test")
        parsed = yaml.safe_load(text)
        assert parsed["server"] == "example.com:443"
        assert parsed["auth"] == "cfg-pass"

    def test_backup_creates_file(self, tmp_path: Path) -> None:
        import asyncio

        config_path = tmp_path / "config.yaml"
        save_config(config_path, _make_hysteria_config())
        backups_dir = tmp_path / "backups"

        adapter = Hysteria2Adapter(
            config_path=config_path,
            backups_dir=backups_dir,
            public_host="1.2.3.4",
        )
        result = asyncio.run(adapter.backup_config())
        assert result is not None
        assert Path(result).exists()
        assert "hysteria-config-" in Path(result).name

    def test_backup_returns_none_if_no_config(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        adapter = Hysteria2Adapter(
            config_path=tmp_path / "nonexistent.yaml",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        result = asyncio.run(adapter.backup_config())
        assert result is None

    def test_collect_traffic_returns_empty_without_config(
        self, tmp_path: Path
    ) -> None:
        import asyncio

        adapter = Hysteria2Adapter(
            config_path=tmp_path / "nonexistent.yaml",
            backups_dir=tmp_path / "backups",
            public_host="1.2.3.4",
        )
        result = asyncio.run(adapter.collect_traffic())
        assert result == {}
