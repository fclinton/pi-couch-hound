"""Tests for SSL configuration and certificate generation."""

from __future__ import annotations

import datetime
import tempfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from couch_hound.config import AppConfig, SslConfig, WebConfig, load_config, save_config
from couch_hound.ssl_certs import _is_cert_expiring, ensure_ssl_files


def _write_cert_expiring_in(cert_path: Path, key_path: Path, days: int) -> None:
    """Write a self-signed cert that expires in *days* days (negative = already expired)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=365))
        .not_valid_after(now + datetime.timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def test_default_ssl_config():
    """Default SSL config should be disabled."""
    config = AppConfig()
    assert config.web.ssl.enabled is False
    assert config.web.ssl.certfile is None
    assert config.web.ssl.keyfile is None
    assert config.web.ssl.self_signed is False


def test_ssl_disabled_no_validation():
    """Disabled SSL should not require any cert settings."""
    ssl = SslConfig(enabled=False)
    assert ssl.enabled is False


def test_ssl_requires_keyfile_with_certfile(tmp_path: Path):
    """Providing certfile without keyfile should fail."""
    cert = tmp_path / "cert.pem"
    cert.write_text("fake")
    with pytest.raises(Exception, match="Both certfile and keyfile"):
        SslConfig(enabled=True, certfile=str(cert))


def test_ssl_requires_certfile_with_keyfile(tmp_path: Path):
    """Providing keyfile without certfile should fail."""
    key = tmp_path / "key.pem"
    key.write_text("fake")
    with pytest.raises(Exception, match="Both certfile and keyfile"):
        SslConfig(enabled=True, keyfile=str(key))


def test_ssl_requires_cert_or_self_signed():
    """Enabled SSL with no certs and no self_signed should fail."""
    with pytest.raises(Exception, match="no certfile/keyfile or self_signed"):
        SslConfig(enabled=True)


def test_ssl_valid_self_signed():
    """Self-signed mode should be valid without cert paths."""
    ssl = SslConfig(enabled=True, self_signed=True)
    assert ssl.self_signed is True


def test_ssl_valid_with_cert_paths(tmp_path: Path):
    """Providing both certfile and keyfile should succeed."""
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("fake cert")
    key.write_text("fake key")
    ssl = SslConfig(enabled=True, certfile=str(cert), keyfile=str(key))
    assert ssl.certfile == str(cert)
    assert ssl.keyfile == str(key)


def test_ssl_nonexistent_certfile(tmp_path: Path):
    """Non-existent certfile should fail validation."""
    key = tmp_path / "key.pem"
    key.write_text("fake")
    with pytest.raises(Exception, match="certfile not found"):
        SslConfig(enabled=True, certfile="/nonexistent/cert.pem", keyfile=str(key))


def test_ssl_nonexistent_keyfile(tmp_path: Path):
    """Non-existent keyfile should fail validation."""
    cert = tmp_path / "cert.pem"
    cert.write_text("fake")
    with pytest.raises(Exception, match="keyfile not found"):
        SslConfig(enabled=True, certfile=str(cert), keyfile="/nonexistent/key.pem")


def test_ssl_config_roundtrip(tmp_path: Path):
    """SSL config should round-trip through YAML."""
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("fake cert")
    key.write_text("fake key")

    config = AppConfig(
        web=WebConfig(ssl=SslConfig(enabled=True, certfile=str(cert), keyfile=str(key)))
    )

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    save_config(config, path)
    loaded = load_config(path)
    assert loaded.web.ssl.enabled is True
    assert loaded.web.ssl.certfile == str(cert)
    assert loaded.web.ssl.keyfile == str(key)
    path.unlink()


def test_ensure_ssl_files_self_signed(tmp_path: Path):
    """Self-signed mode should generate cert and key files."""
    ssl = SslConfig(enabled=True, self_signed=True)
    certfile, keyfile = ensure_ssl_files(ssl, cert_dir=tmp_path)
    assert Path(certfile).exists()
    assert Path(keyfile).exists()
    assert certfile.endswith(".pem")
    assert keyfile.endswith(".pem")


def test_ensure_ssl_files_reuses_existing(tmp_path: Path):
    """Self-signed certs should be reused if already generated."""
    ssl = SslConfig(enabled=True, self_signed=True)
    cert1, key1 = ensure_ssl_files(ssl, cert_dir=tmp_path)
    cert2, key2 = ensure_ssl_files(ssl, cert_dir=tmp_path)
    assert cert1 == cert2
    assert key1 == key2
    # File content should be identical (not regenerated)
    assert Path(cert1).read_bytes() == Path(cert2).read_bytes()


def test_ensure_ssl_files_provided_paths(tmp_path: Path):
    """Provided cert paths should be returned as-is."""
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("fake cert")
    key.write_text("fake key")

    ssl = SslConfig(enabled=True, certfile=str(cert), keyfile=str(key))
    result_cert, result_key = ensure_ssl_files(ssl)
    assert result_cert == str(cert)
    assert result_key == str(key)


def test_self_signed_key_permissions(tmp_path: Path):
    """Self-signed key file should have restricted permissions."""
    ssl = SslConfig(enabled=True, self_signed=True)
    _, keyfile = ensure_ssl_files(ssl, cert_dir=tmp_path)
    import stat

    mode = Path(keyfile).stat().st_mode
    assert not (mode & stat.S_IRGRP)
    assert not (mode & stat.S_IROTH)


def test_is_cert_expiring_fresh_cert(tmp_path: Path):
    """A freshly generated cert (365 days) should not be considered expiring."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    _write_cert_expiring_in(cert_path, key_path, days=365)
    assert _is_cert_expiring(cert_path) is False


def test_is_cert_expiring_near_expiry(tmp_path: Path):
    """A cert expiring within the threshold should be considered expiring."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    _write_cert_expiring_in(cert_path, key_path, days=3)
    assert _is_cert_expiring(cert_path, threshold_days=7) is True


def test_is_cert_expiring_already_expired(tmp_path: Path):
    """An already-expired cert should be considered expiring."""
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    _write_cert_expiring_in(cert_path, key_path, days=-1)
    assert _is_cert_expiring(cert_path) is True


def test_is_cert_expiring_corrupt_file(tmp_path: Path):
    """A corrupt cert file should be treated as expired."""
    cert_path = tmp_path / "cert.pem"
    cert_path.write_bytes(b"not a real certificate")
    assert _is_cert_expiring(cert_path) is True


def test_ensure_ssl_files_regenerates_expiring(tmp_path: Path):
    """An expiring cert should be regenerated by ensure_ssl_files."""
    cert_path = tmp_path / "self-signed.pem"
    key_path = tmp_path / "self-signed-key.pem"
    _write_cert_expiring_in(cert_path, key_path, days=3)
    old_content = cert_path.read_bytes()

    ssl = SslConfig(enabled=True, self_signed=True)
    ensure_ssl_files(ssl, cert_dir=tmp_path)

    new_content = cert_path.read_bytes()
    assert new_content != old_content

    # Verify the new cert has ~365 days validity
    cert = x509.load_pem_x509_certificate(new_content)
    remaining = cert.not_valid_after_utc - datetime.datetime.now(datetime.UTC)
    assert remaining.days >= 360
