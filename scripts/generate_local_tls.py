"""Generate a self-signed TLS certificate for secure Android-to-PC LAN access.

The certificate is pinned by SHA-256 fingerprint inside the Android app.
The private key and certificate are written under data/ and are ignored by Git.
"""
from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CERT_PATH = DATA_DIR / "local-server-cert.pem"
KEY_PATH = DATA_DIR / "local-server-key.pem"


def local_ipv4_addresses() -> set[str]:
    found: set[str] = set()
    hostname = socket.gethostname()

    try:
        for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            candidate = item[4][0]
            address = ipaddress.ip_address(candidate)
            if address.is_private and not address.is_loopback and not address.is_link_local:
                found.add(str(address))
    except OSError:
        pass

    # UDP connect only asks the OS which local interface would be used; it sends no packet.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            candidate = probe.getsockname()[0]
            address = ipaddress.ip_address(candidate)
            if address.is_private and not address.is_loopback and not address.is_link_local:
                found.add(str(address))
    except OSError:
        pass

    return found


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    hostname = socket.gethostname()

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Aleena Local PC"),
    ])

    dns_names = {"localhost", hostname}
    sans: list[x509.GeneralName] = [
        x509.DNSName(name) for name in sorted(dns_names)
    ]
    sans.extend([
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ])

    addresses = local_ipv4_addresses()
    sans.extend(
        x509.IPAddress(ipaddress.ip_address(value))
        for value in sorted(addresses)
    )

    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    KEY_PATH.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    CERT_PATH.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
    print("\nALEENA LOCAL TLS CERTIFICATE CREATED")
    print(f"Certificate: {CERT_PATH}")
    print(f"Private key: {KEY_PATH}")
    print(f"SHA-256 fingerprint (copy exactly into Android):\n{fingerprint}")
    print("\nLocal PC addresses discovered:")
    for address in sorted(addresses):
        print(f"  https://{address}:8767")
    print("\nKeep the private key on this PC. Never upload either PEM file to GitHub.")
    print("If your PC changes Wi-Fi adapter or IP address, rerun this script and update the app pin if the certificate is regenerated.")


if __name__ == "__main__":
    main()
