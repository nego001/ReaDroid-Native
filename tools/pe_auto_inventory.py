#!/usr/bin/env python3
"""Safe, read-only PE32/PE32+ inventory for a future one-click reverse pipeline.

This module does not run the supplied executable, unpack it, disassemble code,
identify functions or upload its bytes. All evidence comes from bounded PE
headers and section-table fields. It intentionally treats unknown metadata as
unknown rather than pretending to have recovered source code.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import struct
import sys

MAX_FILE_BYTES = 1024 * 1024 * 1024
MAX_PE_OFFSET = 1024 * 1024
MAX_OPTIONAL_BYTES = 4096
MAX_SECTIONS = 96
MACHINE = {0x14C: "x86", 0x8664: "x86_64", 0xAA64: "arm64"}
DIRECTORIES = ("exports", "imports", "resources", "exceptions", "certificates",
               "base_relocations", "debug", "architecture", "global_pointer",
               "tls", "load_config", "bound_import", "iat", "delay_import",
               "clr", "reserved")


class PEProbeError(ValueError):
    """Input is malformed, unsupported, or outside the audit budget."""


def _read_at(stream, offset: int, length: int, file_size: int) -> bytes:
    if offset < 0 or length < 0 or offset > file_size - length:
        raise PEProbeError("PE: leitura fora do tamanho do arquivo")
    stream.seek(offset)
    payload = stream.read(length)
    if len(payload) != length:
        raise PEProbeError("PE: leitura truncada")
    return payload


def _u16(buffer: bytes, offset: int) -> int:
    return struct.unpack_from("<H", buffer, offset)[0]


def _u32(buffer: bytes, offset: int) -> int:
    return struct.unpack_from("<I", buffer, offset)[0]


def inspect_pe(path: str | Path) -> dict:
    """Return a strict JSON-safe header inventory, never execute *path*."""
    target = Path(path)
    if target.is_symlink():
        raise PEProbeError("PE: links simbólicos não são aceitos")
    try:
        mode = target.stat().st_mode
        length = target.stat().st_size
    except OSError as exc:
        raise PEProbeError("PE: arquivo indisponível") from exc
    if not stat.S_ISREG(mode) or length < 128 or length > MAX_FILE_BYTES:
        raise PEProbeError("PE: tipo ou tamanho de arquivo não permitido")

    with target.open("rb") as stream:
        dos = _read_at(stream, 0, 64, length)
        if dos[:2] != b"MZ":
            raise PEProbeError("PE: assinatura MZ ausente")
        pe_offset = _u32(dos, 0x3C)
        if pe_offset < 64 or pe_offset > MAX_PE_OFFSET:
            raise PEProbeError("PE: e_lfanew fora da cota")
        coff = _read_at(stream, pe_offset, 24, length)
        if coff[:4] != bytes((80,69,0,0)):
            raise PEProbeError("PE: assinatura PE inválida")
        machine, section_count, timestamp, _, _, optional_size, flags = (
            struct.unpack_from("<HHIIIHH", coff, 4))
        if machine not in MACHINE:
            raise PEProbeError("PE: arquitetura não suportada")
        if section_count == 0 or section_count > MAX_SECTIONS:
            raise PEProbeError("PE: quantidade de seções inválida")
        if optional_size < 96 or optional_size > MAX_OPTIONAL_BYTES:
            raise PEProbeError("PE: cabeçalho opcional inválido")
        optional_offset = pe_offset + 24
        optional = _read_at(stream, optional_offset, optional_size, length)
        magic = _u16(optional, 0)
        if magic == 0x10B:
            format_name = "PE32"
            dir_count_offset, dir_start = 92, 96
            if machine != 0x14C:
                raise PEProbeError("PE32 com arquitetura não suportada")
        elif magic == 0x20B:
            format_name = "PE32+"
            dir_count_offset, dir_start = 108, 112
            if machine not in (0x8664, 0xAA64):
                raise PEProbeError("PE32+ com arquitetura não suportada")
        else:
            raise PEProbeError("PE: tipo de imagem opcional desconhecido")
        if optional_size < dir_start:
            raise PEProbeError("PE: cabeçalho opcional truncado")
        declared_directory_count = _u32(optional, dir_count_offset)
        if declared_directory_count > 16:
            raise PEProbeError("PE: contador de diretórios inválido")
        if dir_start + declared_directory_count * 8 > optional_size:
            raise PEProbeError("PE: tabela de diretórios truncada")

        # Section headers: 40 bytes each. Data is not read from sections.
        section_table = optional_offset + optional_size
        table_bytes = section_count * 40
        section_headers = _read_at(stream, section_table, table_bytes, length)
        sections = []
        for index in range(section_count):
            record = section_headers[index * 40:(index + 1) * 40]
            raw_name = record[:8].split(bytes((0,)), 1)[0]
            if not raw_name or any(b < 32 or b > 126 for b in raw_name):
                raise PEProbeError("PE: nome de seção inválido")
            virtual_size, rva, disk_bytes, disk_offset = struct.unpack_from("<IIII", record, 8)
            if disk_bytes and (disk_offset < section_table + table_bytes
                               or disk_offset > length - disk_bytes):
                raise PEProbeError("PE: seção aponta para bytes fora do arquivo")
            sections.append({
                "name": raw_name.decode("ascii"),
                "rva": rva,
                "virtual_size": virtual_size,
                "raw_offset": disk_offset,
                "raw_size": disk_bytes,
            })

        directories = {}
        for index in range(declared_directory_count):
            rva_or_file_offset = _u32(optional, dir_start + index * 8)
            size = _u32(optional, dir_start + index * 8 + 4)
            directories[DIRECTORIES[index]] = {
                "address": rva_or_file_offset,
                "bytes": size,
                "present": bool(rva_or_file_offset and size),
            }
        subsystem = _u16(optional, 68)
        return {
            "schema": "pe_header_inventory_v1",
            "format": format_name,
            "architecture": MACHINE[machine],
            "file_bytes": length,
            "entry_point_rva": _u32(optional, 16),
            "subsystem": subsystem,
            "is_dll": bool(flags & 0x2000),
            "sections": sections,
            "directories": directories,
            "analysis": {
                "status": "header-only",
                "automatic_function_identification": "not_implemented",
                "decompilation": "not_implemented",
                "file_executed": False,
                "file_uploaded": False,
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventário PE offline, sem execução")
    parser.add_argument("binary", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect_pe(args.binary)
    except PEProbeError as error:
        print(json.dumps({"status": "rejected", "reason": str(error)},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
