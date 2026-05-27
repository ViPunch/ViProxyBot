from urllib.parse import unquote, urlparse

from src.infrastructure.protocols.vless.link_generator import generate_vless_link


def test_generate_vless_link_format() -> None:
    link = generate_vless_link('uuid-123', '1.2.3.4', 443, remark='Test User')

    parsed = urlparse(link)
    assert parsed.scheme == 'vless'
    assert parsed.hostname == '1.2.3.4'
    assert parsed.port == 443
    assert parsed.username == 'uuid-123'
    assert unquote(parsed.fragment) == 'Test User'
