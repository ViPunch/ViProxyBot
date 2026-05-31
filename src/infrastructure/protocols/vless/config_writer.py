from __future__ import annotations

import json
from pathlib import Path


def create_initial_config(config_path: Path, listen_port: int) -> None:
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": listen_port,
                "protocol": "vless",
                "settings": {
                    "clients": [],
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "tls",
                },
            }
        ],
        "outbounds": [{"protocol": "freedom"}],
    }
    save_config(config_path, config)


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config(config_path: Path, config: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add_client_to_config(config: dict, uuid: str, email: str) -> dict:
    updated_config = json.loads(json.dumps(config))
    settings = updated_config["inbounds"][0].setdefault("settings", {})
    clients = settings.pop("users", None)
    if clients is None:
        clients = settings.setdefault("clients", [])
    else:
        settings["clients"] = clients

    if any(u.get("email") == email for u in clients):
        raise ValueError(f"Client with email '{email}' already exists")
    clients.append({
        "id": uuid,
        "email": email,
        "flow": "xtls-rprx-vision",
    })
    return updated_config


def remove_client_from_config(config: dict, email: str) -> dict:
    updated_config = json.loads(json.dumps(config))
    settings = updated_config["inbounds"][0].setdefault("settings", {})
    clients = settings.pop("users", None)
    if clients is None:
        clients = settings.get("clients", [])
    settings["clients"] = [
        client for client in clients if client.get("email") != email
    ]
    return updated_config


def get_clients_from_config(config: dict) -> list[dict]:
    settings = config["inbounds"][0].get("settings", {})
    clients = settings.get("clients")
    if clients is not None:
        return list(clients)
    return list(settings.get("users", []))


def get_listen_port_from_config(config: dict) -> int:
    return int(config["inbounds"][0]["port"])
