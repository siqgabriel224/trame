"""Preparação offline do servidor Windows. Não abre firewall nem instala confiança."""

import argparse
import ipaddress
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def configure(home, hostname, address, port=18743):
    address = ipaddress.ip_address(address)
    if (
        address.is_loopback
        or address.is_unspecified
        or address.is_multicast
        or not address.is_private
    ):
        raise ValueError("Informe o IPv4 privado e fixo do computador servidor na empresa.")
    if address.version != 4 or not 1024 <= port <= 65535:
        raise ValueError("Use IPv4 e porta entre 1024 e 65535.")
    import re

    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?", hostname):
        raise ValueError(
            "Nome do servidor inválido. Use o nome DNS do computador, sem barras ou espaços."
        )
    folder = home / "certificados"
    if (home / "rede.json").exists() or folder.exists():
        raise ValueError(
            "Já existe configuração ou pasta de certificados. Preserve uma cópia e revise com a TI antes de reconfigurar."
        )
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Trame - Autoridade interna " + hostname)]
    )
    ca = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1095))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName(hostname),
                    x509.IPAddress(address),
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    folder.mkdir()
    (folder / "autoridade.cer").write_bytes(ca.public_bytes(serialization.Encoding.DER))
    (folder / "servidor.pem").write_bytes(
        cert.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM)
    )
    (folder / "servidor-chave.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    # A chave da CA não é persistida: não pode emitir certificados para outros serviços.
    config = {
        "bind": str(address),
        "port": port,
        "public_url": f"https://{address}:{port}",
        "cert": "certificados/servidor.pem",
        "key": "certificados/servidor-chave.pem",
    }
    (home / "rede.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fingerprint = ca.fingerprint(hashes.SHA256()).hex(":").upper()
    (folder / "LEIA-PRIMEIRO.txt").write_text(
        "Certificado público para a TI instalar nos computadores clientes: autoridade.cer\nSHA256: "
        + fingerprint
        + "\nSomente o certificado público pode ser distribuído. Não compartilhe servidor-chave.pem.\nCertificado do servidor expira em: "
        + cert.not_valid_after_utc.isoformat()
        + "\nAntes de expirar, a TI deve substituir certificado e chave e distribuir a nova confiança.\n",
        encoding="utf-8",
    )
    return config["public_url"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, default=18743)
    args = parser.parse_args()
    print(configure(Path(__file__).resolve().parent, args.host, args.ip, args.port))
