"""SSL certificate utilities for HTTPS support."""

from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from couch_hound.config import SslConfig

logger = logging.getLogger(__name__)

SELF_SIGNED_DIR = Path("certs")
SELF_SIGNED_CERT = SELF_SIGNED_DIR / "self-signed.pem"
SELF_SIGNED_KEY = SELF_SIGNED_DIR / "self-signed-key.pem"


def _generate_self_signed(cert_path: Path, key_path: Path) -> None:
    """Generate a self-signed certificate and private key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Pi Couch Hound"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)

    # Write key with restricted permissions
    fd = os.open(str(key_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(
            fd,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ),
        )
    finally:
        os.close(fd)

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    logger.info("Generated self-signed certificate at %s", cert_path)


def ensure_ssl_files(
    ssl_config: SslConfig,
    cert_dir: Path | None = None,
) -> tuple[str, str]:
    """Return (certfile, keyfile) paths, generating self-signed if needed."""
    if ssl_config.certfile and ssl_config.keyfile:
        return ssl_config.certfile, ssl_config.keyfile

    base = cert_dir or SELF_SIGNED_DIR
    cert_path = base / "self-signed.pem"
    key_path = base / "self-signed-key.pem"

    if not cert_path.exists() or not key_path.exists():
        _generate_self_signed(cert_path, key_path)

    return str(cert_path), str(key_path)
