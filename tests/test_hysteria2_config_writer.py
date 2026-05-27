from pathlib import Path

from src.infrastructure.protocols.hysteria2.config_writer import (
    create_server_config,
    get_auth_password,
    get_listen_port,
    get_stats_endpoint,
    get_stats_secret,
    load_config,
    update_auth_password,
)


def test_create_and_load_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    create_server_config(
        config_path,
        listen_port=8443,
        cert_path="/etc/cert.pem",
        key_path="/etc/key.pem",
        auth_password="test-pass",
        stats_listen="127.0.0.1:25199",
        stats_secret="secret123",
    )
    config = load_config(config_path)
    assert get_listen_port(config) == 8443
    assert get_auth_password(config) == "test-pass"
    assert get_stats_endpoint(config) == "http://127.0.0.1:25199"
    assert get_stats_secret(config) == "secret123"


def test_update_auth_password() -> None:
    config = {
        "listen": ":443",
        "auth": {"type": "password", "password": "old"},
    }
    updated = update_auth_password(config, "new-pass")
    assert get_auth_password(updated) == "new-pass"
    assert config["auth"]["password"] == "old"
