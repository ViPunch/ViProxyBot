from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from src import cli


def test_status_uses_systemctl(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(cli, "require_command", lambda *_args: None)
    monkeypatch.setattr(
        cli,
        "run_system_command",
        lambda command: commands.append(command) or 0,
    )

    exit_code = cli.handle_command(Namespace(command="status"))

    assert exit_code == 0
    assert commands == [["systemctl", "status", cli.SERVICE_NAME]]


def test_enable_uses_systemctl(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(cli, "require_command", lambda *_args: None)
    monkeypatch.setattr(
        cli,
        "run_system_command",
        lambda command: commands.append(command) or 0,
    )

    exit_code = cli.handle_command(Namespace(command="enable"))

    assert exit_code == 0
    assert commands == [["systemctl", "enable", cli.SERVICE_NAME]]


def test_logs_supports_lines_and_follow(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(cli, "require_command", lambda *_args: None)
    monkeypatch.setattr(
        cli,
        "run_system_command",
        lambda command: commands.append(command) or 0,
    )

    exit_code = cli.handle_command(Namespace(command="logs", lines=25, follow=True))

    assert exit_code == 0
    assert commands == [["journalctl", "-u", cli.SERVICE_NAME, "-n", "25", "-f"]]


def test_run_uses_installed_run_script(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(cli, "RUN_SCRIPT", Path("/tmp/run.sh"))
    monkeypatch.setattr(Path, "is_file", lambda self: self == Path("/tmp/run.sh"))
    monkeypatch.setattr(
        cli,
        "run_system_command",
        lambda command: commands.append(command) or 0,
    )

    exit_code = cli.handle_command(Namespace(command="run"))

    assert exit_code == 0
    assert commands == [[str(Path("/tmp/run.sh"))]]


def test_run_fails_without_run_script(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "RUN_SCRIPT", Path("/tmp/missing.sh"))

    with pytest.raises(SystemExit, match="Run script not found"):
        cli.handle_command(Namespace(command="run"))


def test_update_uses_project_script(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []
    update_script = Path("/opt/vpnbot/app/scripts/update.sh")

    monkeypatch.setattr(cli, "APP_ROOT", Path("/opt/vpnbot"))
    monkeypatch.setattr(Path, "is_file", lambda self: self == update_script)
    monkeypatch.setattr(
        cli,
        "run_system_command",
        lambda command: commands.append(command) or 0,
    )

    exit_code = cli.handle_command(Namespace(command="update"))

    assert exit_code == 0
    assert commands == [["bash", str(update_script)]]


def test_main_without_args_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage: vi-proxy" in captured.out
