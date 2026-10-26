#!/usr/bin/env python3
"""PE-A1: static, bounded PE import/export table extraction, without execution.

This deliberately does not run a Windows executable, launch an emulator,
decode instructions, recover source, discover local functions, or upload data.
It only reads file-backed PE section bytes and reports imports/exports.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

from pe_auto_inventory import PEProbeError, inspect_pe

MAX_READ_BYTES = 16 * 1024 * 1024
MAX_IMPORT_DLLS = 128
MAX_IMPORTS_PER_DLL = 512
MAX_TOTAL_IMPORTS = 2048
MAX_EXPORT_FUNCTIONS = 4096
MAX_EXPORT_NAMES = 2048
MAX_REPORTED_EXPORTS = 128
MAX_ASCII_NAME = 256


class RvaReader:
    """Resolve file-backed RVAs using inspected sections, charging every read."""

    def __init__(self, binary, inspection):
        self.binary = binary
        self.sections = inspection["sections"]
        self.length = inspection["file_bytes"]
        self.budget = MAX_READ_BYTES

    def _map(self, rva, size):
        if not isinstance(rva, int) or rva < 0 or size < 1 or rva > 0xFFFFFFFF:
            raise PEProbeError("PE: RVA ou tamanho de leitura inválido")
        hits = []
        for section in self.sections:
            start = section["rva"]
            raw = section["raw_size"]
            if rva >= start and rva - start <= raw - size:
                at = section["raw_offset"] + rva - start
                if at >= 0 and at <= self.length - size:
                    hits.append(at)
        if len(hits) != 1:
            raise PEProbeError("PE: RVA ausente, virtual ou ambíguo nas seções")
        return hits[0]

    def read(self, rva, size):
        position = self._map(rva, size)
        if size > self.budget:
            raise PEProbeError("PE: orçamento acumulado de leitura excedido")
        data = self.binary.read_at(position, size)
        self.budget -= size
        return data

    def u16(self, rva):
        return struct.unpack("<H", self.read(rva, 2))[0]

    def u32(self, rva):
        return struct.unpack("<I", self.read(rva, 4))[0]

    def ascii(self, rva, *, dll=False):
        if rva == 0:
            raise PEProbeError("PE: nome em RVA nulo")
        data = bytearray()
        for _ in range(MAX_ASCII_NAME + 1):
            value = self.read(rva + len(data), 1)[0]
            if value == 0:
                if not data:
                    raise PEProbeError("PE: nome vazio")
                text = data.decode("ascii")
                if dll and any(ch in text for ch in ("/", "\\", ":")):
                    raise PEProbeError("PE: nome de DLL com caminho inesperado")
                return text
            if value < 32 or value > 126:
                raise PEProbeError("PE: nome de import/export não ASCII")
            data.append(value)
        raise PEProbeError("PE: nome de import/export excede o limite")


class Binary:
    def __init__(self, file_path, size):
        self.stream = file_path.open("rb")
        self.length = size

    def read_at(self, offset, size):
        if offset < 0 or size < 0 or offset > self.length - size:
            raise PEProbeError("PE: leitura bruta fora do arquivo")
        self.stream.seek(offset)
        value = self.stream.read(size)
        if len(value) != size:
            raise PEProbeError("PE: leitura bruta truncada")
        return value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stream.close()


def _directory(info, key):
    entry = info["directories"].get(key)
    if not entry:
        return 0, 0
    rva, size = entry["address"], entry["bytes"]
    if (rva == 0) != (size == 0):
        raise PEProbeError("PE: diretório parcialmente nulo")
    return rva, size


def _imports(reader, info):
    rva, size = _directory(info, "imports")
    if rva == 0:
        return []
    if size < 20:
        raise PEProbeError("PE: diretório de imports truncado")
    # A PE import descriptor consists of five uint32 entries; a zero
    # descriptor terminates the list. Never trust a declared count alone.
    max_records = min(size // 20, MAX_IMPORT_DLLS + 1)
    width = 8 if info["format"] == "PE32+" else 4
    flag = 1 << (width * 8 - 1)
    mask = flag - 1
    result = []
    total_imports = 0
    terminated = False
    for i in range(max_records):
        descriptor = reader.read(rva + i * 20, 20)
        if descriptor == bytes(20):
            terminated = True
            break
        if len(result) >= MAX_IMPORT_DLLS:
            raise PEProbeError("PE: quantidade de DLLs excede o orçamento")
        lookup, stamp, forwarder, name_rva, iat_rva = struct.unpack("<IIIII", descriptor)
        if name_rva == 0 or (lookup == 0 and iat_rva == 0):
            raise PEProbeError("PE: descritor de import inválido")
        dll_name = reader.ascii(name_rva, dll=True)
        thunk_rva = lookup if lookup else iat_rva
        members = []
        thunk_ended = False
        for j in range(MAX_IMPORTS_PER_DLL + 1):
            raw = reader.read(thunk_rva + j * width, width)
            thunk = int.from_bytes(raw, "little")
            if thunk == 0:
                thunk_ended = True
                break
            if j >= MAX_IMPORTS_PER_DLL or total_imports >= MAX_TOTAL_IMPORTS:
                raise PEProbeError("PE: quantidade de imports excede o limite")
            if thunk & flag:
                ordinal = thunk & 0xFFFF
                if ordinal == 0 or (thunk & mask) != ordinal:
                    raise PEProbeError("PE: ordinal de import inválido")
                members.append({"by": "ordinal", "ordinal": ordinal})
            else:
                hint_name_rva = thunk & mask
                if hint_name_rva > 0xFFFFFFFF:
                    raise PEProbeError("PE: RVA de import PE32+ inválido")
                hint = reader.u16(hint_name_rva)
                name = reader.ascii(hint_name_rva + 2)
                members.append({"by": "name", "name": name, "hint": hint})
            total_imports += 1
        if not thunk_ended:
            raise PEProbeError("PE: tabela de imports sem terminador")
        result.append({"dll": dll_name, "functions": members,
                       "count": len(members)})
    if not terminated:
        raise PEProbeError("PE: lista de descritores de import sem terminador")
    return result


def _exports(reader, info):
    rva, size = _directory(info, "exports")
    if rva == 0:
        return {"dll_name": None, "count": 0, "named_count": 0,
                "preview_truncated": False, "functions": []}
    if size < 40:
        raise PEProbeError("PE: diretório de exports truncado")
    values = struct.unpack("<IIHHIIIIIII", reader.read(rva, 40))
    (_, _, _, _, name_rva, base, num_functions, num_names, addresses,
     names, ordinals) = values
    if num_functions > MAX_EXPORT_FUNCTIONS or num_names > MAX_EXPORT_NAMES:
        raise PEProbeError("PE: exportações excedem o limite")
    if num_names > num_functions:
        raise PEProbeError("PE: mais nomes de exports do que funções")
    if (num_functions and addresses == 0) or (num_names and
            (names == 0 or ordinals == 0)):
        raise PEProbeError("PE: tabelas de exports ausentes")
    dll_name = reader.ascii(name_rva) if name_rva else None
    func_rvas = (struct.unpack("<" + "I" * num_functions,
                 reader.read(addresses, num_functions * 4))
                 if num_functions else ())
    name_rvas = (struct.unpack("<" + "I" * num_names,
                 reader.read(names, num_names * 4)) if num_names else ())
    name_ordinals = (struct.unpack("<" + "H" * num_names,
                     reader.read(ordinals, num_names * 2)) if num_names else ())
    by_index = {}
    unique_names = set()
    for name_addr, ordinal_index in zip(name_rvas, name_ordinals):
        if ordinal_index >= num_functions:
            raise PEProbeError("PE: ordinal de export fora da tabela")
        name = reader.ascii(name_addr)
        if name in unique_names or ordinal_index in by_index:
            raise PEProbeError("PE: export duplicado")
        unique_names.add(name)
        by_index[ordinal_index] = name
    results = []
    total_nonzero = 0
    for index, func_rva in enumerate(func_rvas):
        if func_rva == 0:
            if index in by_index:
                raise PEProbeError("PE: nome de export aponta para função nula")
            continue
        total_nonzero += 1
        if len(results) >= MAX_REPORTED_EXPORTS:
            continue
        # Forwarders are strings in the export directory, not code addresses.
        forwarding = rva <= func_rva < rva + size
        forwarded_to = reader.ascii(func_rva) if forwarding else None
        results.append({"ordinal": base + index, "name": by_index.get(index),
                        "rva": func_rva, "forwarded_to": forwarded_to})
    return {"dll_name": dll_name, "count": total_nonzero,
            "named_count": num_names,
            "preview_truncated": total_nonzero > MAX_REPORTED_EXPORTS,
            "functions": results}


def inspect_symbols(path):
    """Inventory PE imports/exports without dynamic analysis or code execution."""
    info = inspect_pe(path)
    with Binary(Path(path), info["file_bytes"]) as stream:
        reader = RvaReader(stream, info)
        imported = _imports(reader, info)
        exported = _exports(reader, info)
    return {
        "schema": "pe_symbol_inventory_v1",
        "format": info["format"],
        "architecture": info["architecture"],
        "imports": imported,
        "import_dll_count": len(imported),
        "import_symbol_count": sum(d["count"] for d in imported),
        "exports": exported,
        "analysis": {
            "status": "imports-exports-only",
            "local_function_recovery": "not_implemented",
            "decompilation": "not_implemented",
            "file_executed": False,
            "file_uploaded": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="PE-A1: listar imports/exports sem execução")
    parser.add_argument("binary", type=Path)
    args = parser.parse_args(argv)
    try:
        data = inspect_symbols(args.binary)
    except (PEProbeError, OSError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
