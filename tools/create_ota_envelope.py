#!/usr/bin/env python3
"""Sign NegrescoDroid OTA metadata with an offline RSA release key.

Requires: pip install cryptography
Usage:
  python tools/create_ota_envelope.py --release release.json --key release-private.pem --output signed-release.json
Keep private keys outside the repository and CI logs.
"""
import argparse
import base64
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Sign an OTA release envelope")
    parser.add_argument("--release", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    release = json.loads(Path(args.release).read_text(encoding="utf-8"))
    required = {"versionCode", "versionName", "channel", "downloadUrl", "sha256", "sizeBytes"}
    if not required.issubset(release):
        raise ValueError("Missing release fields: " + ", ".join(sorted(required - release.keys())))
    if release["channel"] not in ("stable", "beta"):
        raise ValueError("Invalid release channel")
    if not str(release["downloadUrl"]).startswith("https://"):
        raise ValueError("Release download must use HTTPS")
    payload = json.dumps(release, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    key = serialization.load_pem_private_key(Path(args.key).read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 3072:
        raise ValueError("Expected RSA private key with at least 3072 bits")
    signature = key.sign(payload.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    envelope = {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}
    target = Path(args.output)
    target.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Signed OTA envelope written to", target)

if __name__ == "__main__":
    main()
