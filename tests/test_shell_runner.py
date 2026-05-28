from src.infrastructure.shell_runner import (
    ShellResult,
    _redact_command,
    _redact_text,
)


class TestRedactText:
    def test_redacts_token(self) -> None:
        assert _redact_text("my-token-123") == "[REDACTED]"

    def test_redacts_secret(self) -> None:
        assert _redact_text("SECRET_VALUE") == "[REDACTED]"

    def test_redacts_password(self) -> None:
        assert _redact_text("db-password") == "[REDACTED]"

    def test_redacts_key(self) -> None:
        assert _redact_text("encryption_key") == "[REDACTED]"

    def test_redacts_uuid(self) -> None:
        assert _redact_text("uuid=abc-123") == "[REDACTED]"

    def test_keeps_safe_text(self) -> None:
        assert _redact_text("/usr/bin/echo") == "/usr/bin/echo"

    def test_case_insensitive(self) -> None:
        assert _redact_text("TOKEN") == "[REDACTED]"
        assert _redact_text("Token") == "[REDACTED]"


class TestRedactCommand:
    def test_redacts_sensitive_parts(self) -> None:
        cmd = ["curl", "-H", "Authorization: Bearer my-token-123"]
        result = _redact_command(cmd)
        assert result[0] == "curl"
        assert result[1] == "-H"
        assert result[2] == "[REDACTED]"

    def test_keeps_safe_parts(self) -> None:
        cmd = ["systemctl", "restart", "vpnbot"]
        assert _redact_command(cmd) == cmd


class TestShellResult:
    def test_success_on_zero_returncode(self) -> None:
        result = ShellResult(returncode=0, stdout="ok", stderr="", success=True)
        assert result.success is True

    def test_failure_on_nonzero_returncode(self) -> None:
        result = ShellResult(returncode=1, stdout="", stderr="err", success=False)
        assert result.success is False

    def test_fields(self) -> None:
        result = ShellResult(
            returncode=42, stdout="out", stderr="err", success=False
        )
        assert result.returncode == 42
        assert result.stdout == "out"
        assert result.stderr == "err"
