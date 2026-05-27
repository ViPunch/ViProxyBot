from __future__ import annotations

from urllib.parse import urlencode


def generate_mtproto_link(
    host: str,
    port: int,
    secret: str,
) -> str:
    params = urlencode({"server": host, "port": port, "secret": secret})
    return f"https://t.me/proxy?{params}"


def generate_mtproto_tg_link(
    host: str,
    port: int,
    secret: str,
) -> str:
    params = urlencode({"server": host, "port": port, "secret": secret})
    return f"tg://proxy?{params}"
