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
from urllib.parse import urlparse
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
    uri = urlparse(str(release["downloadUrl"]))
    if uri.scheme != "https" or not uri.hostname or uri.username or uri.password or uri.fragment:
        raise ValueError("Release download must be an absolute HTTPS URL")
    if not isinstance(release["versionCode"], int) or isinstance(release["versionCode"], bool) or release["versionCode"] < 1:
        raise ValueError("Invalid versionCode")
    if not isinstance(release["sizeBytes"], int) or isinstance(release["sizeBytes"], bool) or not (1 <= release["sizeBytes"] <= 1073741824):
        raise ValueError("Invalid sizeBytes")
    if not isinstance(release["sha256"], str) or len(release["sha256"]) != 64 or any(c not in "0123456789abcdefABCDEF" for c in release["sha256"]):
        raise ValueError("Invalid SHA-256")
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
