from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.infrastructure.shell_runner import run_command

logger = logging.getLogger(__name__)

ACME_HOME = Path("~/.acme.sh").expanduser()
CERT_BASE_DIR = Path("/etc/vpnbot/certs")


@dataclass
class CertificateResult:
    success: bool
    cert_path: str
    key_path: str
    error: str | None = None


async def install_acme() -> bool:
    if (ACME_HOME / "acme.sh").exists():
        return True
    logger.info("Installing acme.sh")
    result = await run_command(
        ["sudo", "/usr/local/bin/vpnbot-ctl", "acme", "install"],
        timeout=60.0,
    )
    return result.success


async def issue_certificate(
    host: str,
    port: int = 80,
    *,
    is_ip: bool = False,
) -> CertificateResult:
    sub = "ip" if is_ip else host
    cert_dir = CERT_BASE_DIR / sub
    cert_path = cert_dir / "fullchain.pem"
    key_path = cert_dir / "privkey.pem"

    if cert_path.exists() and key_path.exists():
        return CertificateResult(
            success=True,
            cert_path=str(cert_path),
            key_path=str(key_path),
        )

    if not await install_acme():
        return CertificateResult(
            success=False,
            cert_path="",
            key_path="",
            error="Failed to install acme.sh",
        )

    action = "issue-ip" if is_ip else "issue-domain"
    logger.info("Issuing certificate for %s", host)
    issue_result = await run_command(
        [
            "sudo", "/usr/local/bin/vpnbot-ctl",
            "cert", action, host, str(port),
        ],
        timeout=120.0,
    )

    if not issue_result.success:
        return CertificateResult(
            success=False,
            cert_path="",
            key_path="",
            error=f"Certificate issuance failed: {issue_result.stderr}",
        )

    install_result = await run_command(
        [
            "sudo", "/usr/local/bin/vpnbot-ctl",
            "cert", "install-cert",
            host, str(key_path), str(cert_path),
        ],
        timeout=30.0,
    )

    if not install_result.success:
        return CertificateResult(
            success=False,
            cert_path="",
            key_path="",
            error=f"Certificate install failed: {install_result.stderr}",
        )

    await run_command(
        ["sudo", "/usr/local/bin/vpnbot-ctl", "file", "chmod", "600", str(key_path)]
    )
    await run_command(
        ["sudo", "/usr/local/bin/vpnbot-ctl", "file", "chmod", "644", str(cert_path)]
    )

    return CertificateResult(
        success=True,
        cert_path=str(cert_path),
        key_path=str(key_path),
    )


async def generate_self_signed_cert(
    domain: str,
) -> CertificateResult:
    cert_dir = CERT_BASE_DIR / "selfsigned"
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        return CertificateResult(
            success=True,
            cert_path=str(cert_path),
            key_path=str(key_path),
        )

    result = await run_command(
        [
            "sudo", "/usr/local/bin/vpnbot-ctl",
            "cert", "selfsigned", domain, str(cert_dir),
        ],
        timeout=30.0,
    )

    if not result.success:
        return CertificateResult(
            success=False,
            cert_path="",
            key_path="",
            error=f"Self-signed cert generation failed: {result.stderr}",
        )

    await run_command(
        ["sudo", "/usr/local/bin/vpnbot-ctl", "file", "chmod", "600", str(key_path)]
    )
    await run_command(
        ["sudo", "/usr/local/bin/vpnbot-ctl", "file", "chmod", "644", str(cert_path)]
    )

    return CertificateResult(
        success=True,
        cert_path=str(cert_path),
        key_path=str(key_path),
    )


async def ensure_certificates(
    ssl_mode: str,
    public_host: str,
    domain: str = "",
    cert_path: str = "",
    key_path: str = "",
) -> CertificateResult:
    if ssl_mode == "domain":
        if not domain:
            return CertificateResult(
                success=False,
                cert_path="",
                key_path="",
                error="Domain is required for ssl_mode=domain",
            )
        return await issue_certificate(domain)

    if ssl_mode == "custom":
        if not cert_path or not key_path:
            return CertificateResult(
                success=False,
                cert_path="",
                key_path="",
                error="cert_path and key_path required for ssl_mode=custom",
            )
        cp = Path(cert_path)
        kp = Path(key_path)
        if not cp.exists() or not kp.exists():
            return CertificateResult(
                success=False,
                cert_path=cert_path,
                key_path=key_path,
                error=f"Certificate files not found: {cp}, {kp}",
            )
        return CertificateResult(
            success=True,
            cert_path=cert_path,
            key_path=key_path,
        )

    host = domain or public_host
    if not host:
        return CertificateResult(
            success=False,
            cert_path="",
            key_path="",
            error="No host available for self-signed cert",
        )
    return await generate_self_signed_cert(host)
