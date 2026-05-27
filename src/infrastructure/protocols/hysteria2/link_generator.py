from __future__ import annotations

from urllib.parse import quote, urlencode

import yaml


def generate_hysteria2_uri(
    host: str,
    port: int,
    password: str,
    *,
    remark: str = "Hysteria2",
    insecure: bool = False,
) -> str:
    params: dict[str, str] = {}
    if insecure:
        params["insecure"] = "1"
    query = urlencode(params)
    uri = f"hysteria2://{password}@{host}:{port}"
    if query:
        uri += f"?{query}"
    uri += f"#{quote(remark)}"
    return uri


def generate_hysteria2_client_config_text(
    host: str,
    port: int,
    password: str,
    *,
    insecure: bool = False,
) -> str:
    config = {
        "server": f"{host}:{port}",
        "auth": password,
        "tls": {"sni": host, "insecure": insecure},
    }
    return yaml.dump(config, default_flow_style=False, allow_unicode=True)
