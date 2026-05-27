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
        [
            "sudo", "bash", "-c",
            "curl -fsSL https://get.acme.sh | sh",
        ],
        timeout=60.0,
    )
    return result.success


async def issue_ip_certificate(
    ip: str,
    port: int = 80,
) -> CertificateResult:
    cert_dir = CERT_BASE_DIR / "ip"
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

    await run_command(["sudo", "mkdir", "-p", str(cert_dir)])

    logger.info("Issuing IP certificate for %s", ip)
    issue_result = await run_command(
        [
            "sudo", str(ACME_HOME / "acme.sh"),
            "--issue",
            "-d", ip,
            "--standalone",
            "--server", "letsencrypt",
            "--httpport", str(port),
            "--force",
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
            "sudo", str(ACME_HOME / "acme.sh"),
            "--installcert",
            "-d", ip,
            "--key-file", str(key_path),
            "--fullchain-file", str(cert_path),
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

    await run_command(["sudo", "chmod", "600", str(key_path)])
    await run_command(["sudo", "chmod", "644", str(cert_path)])

    return CertificateResult(
        success=True,
        cert_path=str(cert_path),
        key_path=str(key_path),
    )


async def issue_domain_certificate(
    domain: str,
    port: int = 80,
) -> CertificateResult:
    cert_dir = CERT_BASE_DIR / domain
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

    await run_command(["sudo", "mkdir", "-p", str(cert_dir)])

    logger.info("Issuing domain certificate for %s", domain)
    issue_result = await run_command(
        [
            "sudo", str(ACME_HOME / "acme.sh"),
            "--issue",
            "-d", domain,
            "--standalone",
            "--server", "letsencrypt",
            "--httpport", str(port),
            "--force",
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
            "sudo", str(ACME_HOME / "acme.sh"),
            "--installcert",
            "-d", domain,
            "--key-file", str(key_path),
            "--fullchain-file", str(cert_path),
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

    await run_command(["sudo", "chmod", "600", str(key_path)])
    await run_command(["sudo", "chmod", "644", str(cert_path)])

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

    await run_command(["sudo", "mkdir", "-p", str(cert_dir)])

    result = await run_command(
        [
            "sudo", "openssl", "req", "-x509", "-nodes",
            "-newkey", "ec",
            "-pkeyopt", "ec_paramgen_curve:prime256v1",
            "-days", "3650",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-subj", f"/CN={domain}",
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

    await run_command(["sudo", "chmod", "600", str(key_path)])
    await run_command(["sudo", "chmod", "644", str(cert_path)])

    return CertificateResult(
        success=True,
        cert_path=str(cert_path),
        key_path=str(key_path),
    )
