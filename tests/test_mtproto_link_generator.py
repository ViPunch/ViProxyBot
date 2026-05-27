from src.infrastructure.protocols.mtproto.link_generator import (
    generate_mtproto_link,
    generate_mtproto_tg_link,
)


def test_generate_mtproto_link() -> None:
    link = generate_mtproto_link("proxy.com", 443, "abc123")
    assert "t.me/proxy?" in link
    assert "server=proxy.com" in link
    assert "port=443" in link
    assert "secret=abc123" in link


def test_generate_mtproto_tg_link() -> None:
    link = generate_mtproto_tg_link("proxy.com", 443, "abc123")
    assert link.startswith("tg://proxy?")
    assert "server=proxy.com" in link
