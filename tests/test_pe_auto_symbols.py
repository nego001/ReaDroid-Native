"""PE-A1: synthetic import/export evidence with malicious RVA handling."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("pe_auto_symbols", ROOT / "tools/pe_auto_symbols.py")
pe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pe)


def build_pe(*, is64=False):
    """Nonexecuting PE fixture: imports by name/ordinal and exported forwarder."""
    b = bytearray(0x1000)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3c, 0x80)
    b[0x80:0x84] = b"PE\x00\x00"
    size = 240 if is64 else 224
    machine = 0x8664 if is64 else 0x14c
    struct.pack_into("<HHIIIHH", b, 0x84, machine, 1, 0, 0, 0, size, 0x2002)
    opt = 0x98
    struct.pack_into("<H", b, opt, 0x20b if is64 else 0x10b)
    struct.pack_into("<I", b, opt + 16, 0x1100)
    struct.pack_into("<H", b, opt + 68, 2)
    count_off = 108 if is64 else 92
    dir_off = 112 if is64 else 96
    struct.pack_into("<I", b, opt + count_off, 16)
    struct.pack_into("<II", b, opt + dir_off, 0x1300, 0x100)
    struct.pack_into("<II", b, opt + dir_off + 8, 0x1000, 40)
    sec = opt + size
    b[sec:sec+8] = b".rdata\x00\x00"
    struct.pack_into("<IIII", b, sec + 8, 0xc00, 0x1000, 0xc00, 0x400)

    def at(rva):
        return 0x400 + rva - 0x1000

    # IMAGE_IMPORT_DESCRIPTOR + null sentinel
    struct.pack_into("<IIIII", b, at(0x1000), 0x1090, 0, 0, 0x1070, 0x1090)
    b[at(0x1070):at(0x1070)+13] = b"TOOLSAPI.dll\x00"
    width = 8 if is64 else 4
    ordinal_flag = 1 << (63 if is64 else 31)
    for idx, thunk in enumerate((0x10b0, ordinal_flag | 17, 0)):
        struct.pack_into("<Q" if is64 else "<I",
                         b, at(0x1090)+idx*width, thunk)
    struct.pack_into("<H", b, at(0x10b0), 5)
    b[at(0x10b2):at(0x10b2)+13] = b"ReadRegistry\x00"

    # IMAGE_EXPORT_DIRECTORY + arrays: one named local export and one forwarder.
    struct.pack_into("<IIHHIIIIIII", b, at(0x1300),
                     0, 0, 0, 0, 0x1380, 5, 2, 1, 0x1340, 0x1350, 0x1360)
    struct.pack_into("<II", b, at(0x1340), 0x1200, 0x13c0)
    struct.pack_into("<I", b, at(0x1350), 0x13a0)
    struct.pack_into("<H", b, at(0x1360), 0)
    b[at(0x1380):at(0x1380)+12] = b"TOOLSAPI.dll\x00"
    b[at(0x13a0):at(0x13a0)+11] = b"CleanCache\x00"
    b[at(0x13c0):at(0x13c0)+15] = b"KERNEL32.Sleep\x00"
    return b


class PEImportExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "dummy.dll"

    def tearDown(self):
        self.temp.cleanup()

    def read(self, data):
        self.path.write_bytes(data)
        return pe.inspect_symbols(self.path)

    def rejected(self, data):
        with self.assertRaises(pe.PEProbeError):
            self.read(data)

    def test_imports_and_exports_pe32(self):
        report = self.read(build_pe())
        self.assertEqual(report["schema"], "pe_symbol_inventory_v1")
        self.assertEqual(report["architecture"], "x86")
        self.assertEqual(report["import_dll_count"], 1)
        self.assertEqual(report["import_symbol_count"], 2)
        imported = report["imports"][0]
        self.assertEqual(imported["dll"], "TOOLSAPI.dll")
        self.assertEqual(imported["functions"][0],
                         {"by": "name", "name": "ReadRegistry", "hint": 5})
        self.assertEqual(imported["functions"][1],
                         {"by": "ordinal", "ordinal": 17})
        exported = report["exports"]
        self.assertEqual(exported["count"], 2)
        self.assertEqual(exported["named_count"], 1)
        self.assertEqual(exported["functions"][0]["name"], "CleanCache")
        self.assertEqual(exported["functions"][0]["ordinal"], 5)
        self.assertIsNone(exported["functions"][0]["forwarded_to"])
        self.assertEqual(exported["functions"][1]["forwarded_to"],
                         "KERNEL32.Sleep")
        self.assertEqual(report["analysis"]["local_function_recovery"],
                         "not_implemented")
        self.assertFalse(report["analysis"]["file_executed"])

    def test_imports_and_exports_pe32_plus(self):
        report = self.read(build_pe(is64=True))
        self.assertEqual(report["format"], "PE32+")
        self.assertEqual(report["architecture"], "x86_64")
        self.assertEqual(report["imports"][0]["functions"][1]["ordinal"], 17)
        self.assertEqual(report["exports"]["functions"][1]["forwarded_to"],
                         "KERNEL32.Sleep")

    def test_absent_directories_are_empty_not_guessed(self):
        b = build_pe()
        b[0x98+96:0x98+96+16] = bytes(16)
        report = self.read(b)
        self.assertEqual(report["imports"], [])
        self.assertEqual(report["import_symbol_count"], 0)
        self.assertEqual(report["exports"]["count"], 0)

    def test_reject_unmapped_import_descriptor_rva(self):
        b = build_pe()
        struct.pack_into("<I", b, 0x98+96+8, 0x500000)
        self.rejected(b)

    def test_reject_missing_import_descriptor_terminator(self):
        b = build_pe()
        struct.pack_into("<IIIII", b, 0x400+20, 0x1090, 0, 0, 0x1070, 0x1090)
        self.rejected(b)

    def test_reject_forged_import_name_pointer(self):
        b = build_pe()
        struct.pack_into("<I", b, 0x400 + 0x1090-0x1000, 0xffff0000)
        self.rejected(b)

    def test_reject_import_name_without_null_within_cap(self):
        b = build_pe()
        string_at = 0x400 + (0x10b2 - 0x1000)
        b[string_at:string_at+300] = b"A"*300
        self.rejected(b)

    def test_reject_overlapping_sections_for_same_rva(self):
        b = build_pe()
        # Add a second section that aliases the entire first section.
        sec = 0x98+224
        struct.pack_into("<H", b, 0x86, 2)
        b[sec+40:sec+48] = b".alias\x00\x00"
        struct.pack_into("<IIII", b, sec+48, 0xc00, 0x1000, 0xc00, 0x400)
        self.rejected(b)

    def test_reject_export_ordinal_out_of_bounds(self):
        b = build_pe()
        struct.pack_into("<H", b, 0x400+(0x1360-0x1000), 3)
        self.rejected(b)

    def test_reject_export_name_rva_outside_sections(self):
        b = build_pe()
        struct.pack_into("<I", b, 0x400+(0x1350-0x1000), 0xfffffff0)
        self.rejected(b)

    def test_reject_excessive_export_function_count(self):
        b = build_pe()
        struct.pack_into("<I", b, 0x400+(0x1300-0x1000)+20, 4097)
        self.rejected(b)

    def test_reject_corrupt_forwarder_string(self):
        b = build_pe()
        b[0x400+(0x13c0-0x1000)] = 0xff
        self.rejected(b)

    def test_reject_partial_null_directory(self):
        b = build_pe()
        struct.pack_into("<I", b, 0x98+96+8+4, 0)
        self.rejected(b)

    def test_offline_only_without_pseudocode_claims(self):
        source = (ROOT / "tools/pe_auto_symbols.py").read_text("utf-8")
        for forbidden in ("subprocess", "os.system", "ctypes.WinDLL",
                          "exec(", "requests.", "urllib.request", "read_bytes("):
            self.assertNotIn(forbidden, source)
        self.assertIn('"decompilation": "not_implemented"', source)


if __name__ == "__main__":
    unittest.main()
