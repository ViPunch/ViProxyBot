from urllib.parse import unquote, urlparse

from src.infrastructure.protocols.hysteria2.link_generator import (
    generate_hysteria2_client_config_text,
    generate_hysteria2_uri,
)


def test_generate_hysteria2_uri() -> None:
    uri = generate_hysteria2_uri("1.2.3.4", 443, "pass123", remark="Test")
    assert uri.startswith("hysteria2://pass123@1.2.3.4:443")
    assert unquote(urlparse(uri).fragment) == "Test"


def test_generate_hysteria2_uri_insecure() -> None:
    uri = generate_hysteria2_uri(
        "1.2.3.4", 443, "pass", insecure=True
    )
    assert "insecure=1" in uri


def test_generate_hysteria2_client_config_text() -> None:
    config_text = generate_hysteria2_client_config_text(
        "1.2.3.4", 443, "pass123"
    )
    assert "1.2.3.4:443" in config_text
    assert "pass123" in config_text
