from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
_REDACTION_TOKENS = ("token", "secret", "password", "key", "uuid")


@dataclass(slots=True)
class ShellResult:
    returncode: int
    stdout: str
    stderr: str
    success: bool


def _redact_text(value: str) -> str:
    lowered = value.lower()
    if any(token in lowered for token in _REDACTION_TOKENS):
        return "[REDACTED]"
    return value


def _redact_command(cmd: list[str]) -> list[str]:
    return [_redact_text(part) for part in cmd]


async def run_command(
    cmd: list[str],
    *,
    timeout: float = 30.0,
    check: bool = False,
    cwd: str | None = None,
) -> ShellResult:
    redacted_cmd = _redact_command(cmd)
    logger.debug("Running command", extra={"command": redacted_cmd})

    executable = shutil.which(cmd[0])
    if executable is None:
        if Path(cmd[0]).is_file():
            executable = cmd[0]
        else:
            raise FileNotFoundError(f"Executable not found: {cmd[0]}")

    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            *cmd[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(cwd)) if cwd else None,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        logger.error("Command timed out", extra={"command": redacted_cmd})
        raise TimeoutError(f"Command timed out after {timeout} seconds") from exc

    stdout = stdout_bytes.decode().strip()
    stderr = stderr_bytes.decode().strip()
    returncode = process.returncode if process.returncode is not None else -1
    result = ShellResult(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        success=returncode == 0,
    )

    if check and not result.success:
        logger.error(
            "Command failed",
            extra={
                "command": redacted_cmd,
                "returncode": result.returncode,
                "stderr": _redact_text(result.stderr),
            },
        )
        raise RuntimeError(f"Command failed with exit code {result.returncode}")

    return result
