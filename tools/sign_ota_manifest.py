#!/usr/bin/env python3
"""Create the RSA/SHA-256 signed JSON envelope consumed by OtaManifestVerifier.

Run on a trusted machine with an OFFLINE OTA metadata signing key.
Never commit the private key or print its content.
"""
import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def build_payload(args):
    apk = Path(args.apk)
    if not apk.is_file():
        raise ValueError("Arquivo APK não encontrado")
    size = apk.stat().st_size
    if not 0 < size <= 1073741824:
        raise ValueError("APK fora do limite de 1 GiB")
    if args.version_code < 1 or args.version_code > 2147483647:
        raise ValueError("versionCode inválido")
    if not args.version_name or len(args.version_name) > 80:
        raise ValueError("versionName inválido")
    if args.channel not in ("stable", "beta"):
        raise ValueError("Canal não permitido")
    if len(args.url) > 2048:
        raise ValueError("URL muito longa")
    url = urlsplit(args.url)
    if (url.scheme != "https" or not url.hostname or url.username is not None
            or url.password is not None or url.fragment or url.port not in (None, 443)):
        raise ValueError("URL OTA deve usar HTTPS sem credenciais ou fragmentos")
    notes = Path(args.notes_file).read_text(encoding="utf-8") if args.notes_file else ""
    if len(notes) > 8000:
        raise ValueError("Notas excedem 8000 caracteres")
    digest = hashlib.sha256()
    with apk.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return {
        "versionCode": args.version_code,
        "versionName": args.version_name,
        "channel": args.channel,
        "downloadUrl": args.url,
        "sha256": digest.hexdigest(),
        "sizeBytes": size,
        "notes": notes,
    }


def main():
    parser = argparse.ArgumentParser(description="Assinar manifesto OTA NegrescoDroid")
    parser.add_argument("--apk", required=True, help="APK final já assinado para instalação")
    parser.add_argument("--url", required=True, help="URL HTTPS exata do APK publicado")
    parser.add_argument("--version-code", type=int, required=True)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--channel", choices=("stable", "beta"), required=True)
    parser.add_argument("--private-key", required=True, help="Chave privada RSA PEM OFFLINE")
    parser.add_argument("--notes-file", help="Notas públicas UTF-8")
    parser.add_argument("--output", required=True, help="Destino do JSON público assinado")
    args = parser.parse_args()
    payload = json.dumps(build_payload(args), ensure_ascii=False, separators=(",", ":"))
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(Path(args.private_key))],
        input=payload.encode("utf-8"), capture_output=True, check=True,
    )
    envelope = {
        "payload": payload,
        "signature": base64.b64encode(result.stdout).decode("ascii"),
    }
    output = Path(args.output)
    output.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Manifesto OTA assinado criado:", output)
    print("SHA-256 APK:", json.loads(payload)["sha256"])


if __name__ == "__main__":
    main()
