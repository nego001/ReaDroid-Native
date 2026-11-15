#!/usr/bin/env python3
"""Validate the two user-approved P7 art files without inventing replacements.

Do not use screenshots from the emulator or newly generated artwork as
substitutes for these byte-identical, approved reference PNGs.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "design" / "reference" / "p7"
DIMENSIONS = (1448, 1086)
MAX_BYTES = 64 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
REFERENCES = {
    "negrecodroid_controle_total_de_apks.png":
        "d0232e8a93d793c5cde3d564f90c8c5ecdd870bee497558db0442bf98326461b",
    "identidade_negrecodroid_em_neon_azul.png":
        "25f93465b1ad0da45398201d9718cc070f3ba7fce11f84bf81e973c0b06d2765",
}


class ReferenceValidationError(ValueError):
    pass


def validate_png(path, expected_sha256, dimensions=DIMENSIONS):
    """Check complete PNG structure, CRC, size and exact approved bytes."""
    if not path.is_file():
        raise ReferenceValidationError("Arquivo oficial ausente")
    if path.stat().st_size > MAX_BYTES:
        raise ReferenceValidationError("PNG de referência acima de 64 MiB")
    data = path.read_bytes()
    if not data.startswith(PNG_MAGIC):
        raise ReferenceValidationError("Assinatura PNG inválida")
    position = len(PNG_MAGIC)
    seen_ihdr = False
    seen_iend = False
    actual_dimensions = None
    while position < len(data):
        if len(data) - position < 12:
            raise ReferenceValidationError("Chunk PNG incompleto")
        chunk_length = struct.unpack_from(">I", data, position)[0]
        end = position + 12 + chunk_length
        if end > len(data):
            raise ReferenceValidationError("Tamanho de chunk PNG inválido")
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + chunk_length]
        received_crc = struct.unpack_from(">I", data, position + 8 + chunk_length)[0]
        calculated_crc = zlib.crc32(kind + payload) & 0xffffffff
        if received_crc != calculated_crc:
            raise ReferenceValidationError("CRC PNG divergente")
        if not seen_ihdr:
            if kind != b"IHDR" or chunk_length != 13:
                raise ReferenceValidationError("Cabeçalho IHDR inválido")
            actual_dimensions = struct.unpack_from(">II", payload)
            seen_ihdr = True
        elif kind == b"IHDR":
            raise ReferenceValidationError("IHDR PNG duplicado")
        position = end
        if kind == b"IEND":
            if chunk_length != 0 or position != len(data):
                raise ReferenceValidationError("Final IEND PNG inválido")
            seen_iend = True
            break
    if not seen_ihdr or not seen_iend:
        raise ReferenceValidationError("PNG sem fechamento válido")
    if actual_dimensions != dimensions:
        raise ReferenceValidationError(
            f"Dimensões {actual_dimensions} diferentes de {dimensions}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ReferenceValidationError(
            "SHA-256 diferente da arte aprovada; não substituir silenciosamente")
    return digest


def check_references(directory=REFERENCE_DIR, references=REFERENCES,
                     dimensions=DIMENSIONS):
    """Return (success, result messages), never silently accept missing PNGs."""
    messages = []
    okay = True
    for filename, sha in references.items():
        try:
            digest = validate_png(Path(directory) / filename, sha, dimensions)
            messages.append(f"P7_REFERENCE_PASS {filename} sha256={digest}")
        except (ReferenceValidationError, OSError) as error:
            okay = False
            messages.append(f"P7_REFERENCE_BLOCKED {filename}: {error}")
    return okay, messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=REFERENCE_DIR,
                        help="Diretório com os dois PNGs oficiais")
    args = parser.parse_args()
    okay, messages = check_references(args.directory)
    for message in messages:
        print(message)
    if not okay:
        print("P7.0 bloqueada: faltam os dois PNGs originais íntegros.")
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())
