import ipaddress
import ssl
from pathlib import Path

from cryptography import x509

from app.tls import write_localhost_certificate


def test_writes_certificate_that_tls_accepts_for_localhost(tmp_path: Path) -> None:
    certificate_path = tmp_path / "tls" / "localhost.crt"
    key_path = tmp_path / "tls" / "localhost.key"

    write_localhost_certificate(certificate_path, key_path)

    ssl.create_default_context(ssl.Purpose.CLIENT_AUTH).load_cert_chain(certificate_path, key_path)
    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert names.get_values_for_type(x509.DNSName) == ["localhost"]
    assert names.get_values_for_type(x509.IPAddress) == [ipaddress.ip_address("127.0.0.1")]
    assert oct(key_path.stat().st_mode & 0o777) == "0o600"
