from __future__ import annotations

from urllib.parse import quote, urlencode


def generate_vless_link(
    uuid: str,
    host: str,
    port: int,
    *,
    remark: str = "VLESS",
    network: str = "tcp",
    security: str = "reality",
    flow: str = "xtls-rprx-vision",
    public_key: str = "",
    short_id: str = "",
    sni: str = "",
    fingerprint: str = "chrome",
) -> str:
    params: dict[str, str] = {
        "type": network,
        "security": security,
    }

    if security == "reality":
        params["flow"] = flow
        if public_key:
            params["pbk"] = public_key
        if short_id:
            params["sid"] = short_id
        if sni:
            params["sni"] = sni
        params["fp"] = fingerprint

    query = urlencode(params)
    return f"vless://{uuid}@{host}:{port}?{query}#{quote(remark)}"
