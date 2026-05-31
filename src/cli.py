from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(os.environ.get("VIPROXY_APP_ROOT", "/opt/vpnbot"))
SERVICE_NAME = os.environ.get("VIPROXY_SERVICE_NAME", "vpnbot")
RUN_SCRIPT = APP_ROOT / "run.sh"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vi-proxy",
        description="Manage the installed ViProxyBot service.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("start", "stop", "restart", "status", "enable", "disable"):
        subparsers.add_parser(command)

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument(
        "-n",
        "--lines",
        type=int,
        help="Show the last N log lines",
    )
    logs_parser.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Follow new log entries",
    )

    subparsers.add_parser("run")
    subparsers.add_parser("update")
    return parser


def run_system_command(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def require_command(command_name: str, install_hint: str) -> None:
    if shutil.which(command_name) is None:
        raise SystemExit(f"{command_name} is not available. {install_hint}")


def handle_command(args: argparse.Namespace) -> int:
    if args.command == "run":
        if not RUN_SCRIPT.is_file():
            raise SystemExit(f"Run script not found: {RUN_SCRIPT}")
        return run_system_command([str(RUN_SCRIPT)])

    if args.command == "update":
        update_script = APP_ROOT / "app" / "scripts" / "update.sh"
        if not update_script.is_file():
            raise SystemExit(f"Update script not found: {update_script}")
        return run_system_command(["bash", str(update_script)])

    if args.command == "logs":
        require_command("journalctl", "Use `vi-proxy run` if systemd is unavailable.")
        command = ["journalctl", "-u", SERVICE_NAME]
        if args.lines is not None:
            command.extend(["-n", str(args.lines)])
        if args.follow:
            command.append("-f")
        return run_system_command(command)

    require_command("systemctl", "Use `vi-proxy run` if systemd is unavailable.")
    return run_system_command(["systemctl", args.command, SERVICE_NAME])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return handle_command(args)


if __name__ == "__main__":
    sys.exit(main())
