from __future__ import annotations

from pathlib import Path

import yaml


def create_server_config(
    config_path: Path,
    listen_port: int,
    cert_path: str,
    key_path: str,
    auth_password: str,
    stats_listen: str = "127.0.0.1:25199",
    stats_secret: str = "",
) -> None:
    config = {
        "listen": f":{listen_port}",
        "tls": {
            "cert": cert_path,
            "key": key_path,
        },
        "auth": {
            "type": "password",
            "password": auth_password,
        },
        "trafficStats": {
            "listen": stats_listen,
            "secret": stats_secret,
        },
    }
    save_config(config_path, config)


def load_config(config_path: Path) -> dict:
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def save_config(config_path: Path, config: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(config, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def get_listen_port(config: dict) -> int:
    listen = config.get("listen", ":443")
    if isinstance(listen, str) and listen.startswith(":"):
        return int(listen[1:])
    return int(listen)


def get_auth_password(config: dict) -> str:
    auth = config.get("auth", {})
    return str(auth.get("password", ""))


def update_auth_password(config: dict, new_password: str) -> dict:
    updated = dict(config)
    updated["auth"] = dict(updated.get("auth", {}))
    updated["auth"]["password"] = new_password
    return updated


def get_stats_endpoint(config: dict) -> str | None:
    stats = config.get("trafficStats", {})
    listen = stats.get("listen")
    if listen is None:
        return None
    return f"http://{listen}"


def get_stats_secret(config: dict) -> str:
    stats = config.get("trafficStats", {})
    return str(stats.get("secret", ""))
