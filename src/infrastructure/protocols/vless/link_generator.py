from __future__ import annotations

from urllib.parse import quote, urlencode


def generate_vless_link(
    uuid: str,
    host: str,
    port: int,
    *,
    remark: str = "VLESS",
    network: str = "tcp",
    security: str = "tls",
) -> str:
    query = urlencode({"type": network, "security": security})
    return f"vless://{uuid}@{host}:{port}?{query}#{quote(remark)}"
