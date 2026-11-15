"""Self-signed certificate for serving the sandbox bank callback on https://localhost.

Run `uv run python -m app.tls`, then set the printed YIJI_SSL_* variables in .env."""

import ipaddress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.config import PROJECT_ROOT, get_settings

CERTIFICATE_VALIDITY = timedelta(days=365)


def write_localhost_certificate(certificate_path: Path, key_path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + CERTIFICATE_VALIDITY)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.touch(mode=0o600)
    key_path.chmod(0o600)
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


if __name__ == "__main__":
    tls_dir = get_settings().data_dir / "tls"
    certificate_file, key_file = tls_dir / "localhost.crt", tls_dir / "localhost.key"
    write_localhost_certificate(certificate_file, key_file)

    def shown(path: Path) -> Path:
        return path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path

    print(f"YIJI_SSL_CERTFILE={shown(certificate_file)}")
    print(f"YIJI_SSL_KEYFILE={shown(key_file)}")
