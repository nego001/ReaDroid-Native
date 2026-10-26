"""Offline tests of the PE auto-intake stage, using synthetic nonexecutables."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/pe_auto_inventory.py"
spec = importlib.util.spec_from_file_location("pe_auto_inventory", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_pe(*, machine=0x14C, optional_magic=0x10B, sections=1,
            with_imports=True):
    """Build a minimal PE header fixture, not functional machine code."""
    out = bytearray(0x800)
    out[0:2] = b"MZ"
    struct.pack_into("<I", out, 0x3C, 0x80)
    out[0x80:0x84] = b"PE\x00\x00"
    size_of_optional = 224 if optional_magic == 0x10B else 240
    struct.pack_into("<HHIIIHH", out, 0x84, machine, sections, 0, 0, 0,
                     size_of_optional, 2)
    opt = 0x98
    struct.pack_into("<H", out, opt, optional_magic)
    struct.pack_into("<I", out, opt + 16, 0x1000)
    struct.pack_into("<H", out, opt + 68, 2)
    dd_count = 92 if optional_magic == 0x10B else 108
    dd_base = 96 if optional_magic == 0x10B else 112
    struct.pack_into("<I", out, opt + dd_count, 16)
    if with_imports:
        struct.pack_into("<II", out, opt + dd_base + 8, 0x1200, 40)
    section_at = opt + size_of_optional
    out[section_at:section_at+8] = b".text\x00\x00\x00"
    struct.pack_into("<IIII", out, section_at+8, 0x180, 0x1000, 0x200, 0x400)
    return out


class PETriageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "installer.exe"

    def tearDown(self):
        self.folder.cleanup()

    def save(self, blob):
        self.path.write_bytes(blob)
        return self.path

    def test_valid_pe32_win32_metadata_only(self):
        result = module.inspect_pe(self.save(make_pe()))
        self.assertEqual(result["format"], "PE32")
        self.assertEqual(result["architecture"], "x86")
        self.assertEqual(result["entry_point_rva"], 0x1000)
        self.assertEqual(result["sections"][0]["name"], ".text")
        self.assertTrue(result["directories"]["imports"]["present"])
        self.assertFalse(result["analysis"]["file_executed"])
        self.assertEqual(result["analysis"]["automatic_function_identification"],
                         "not_implemented")

    def test_valid_pe32_plus_x64_and_arm64(self):
        for machine, label in ((0x8664, "x86_64"), (0xAA64, "arm64")):
            with self.subTest(architecture=label):
                result = module.inspect_pe(self.save(
                    make_pe(machine=machine, optional_magic=0x20B)))
                self.assertEqual(result["format"], "PE32+")
                self.assertEqual(result["architecture"], label)

    def test_unknown_binary_or_invalid_pe_header_rejected(self):
        wrong = make_pe()
        wrong[0:2] = b"XX"
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))
        wrong = make_pe()
        wrong[0x80:0x84] = b"NOPE"
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))
        wrong = make_pe()
        struct.pack_into("<I", wrong, 0x3C, module.MAX_PE_OFFSET + 1)
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))

    def test_reject_wrong_architecture_and_optional_header_pair(self):
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(make_pe(machine=0x8664)))
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(make_pe(machine=0x1234)))
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(
                make_pe(machine=0x14C, optional_magic=0x20B)))

    def test_section_bounds_and_count_are_enforced(self):
        wrong = make_pe()
        struct.pack_into("<H", wrong, 0x86, 97)
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))
        wrong = make_pe()
        section = 0x98 + 224
        struct.pack_into("<I", wrong, section + 20, len(wrong) - 2)
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))
        wrong = make_pe()
        struct.pack_into("<H", wrong, 0x94, 4095)
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))

    def test_directory_count_beyond_header_rejected(self):
        wrong = make_pe()
        struct.pack_into("<I", wrong, 0x98 + 92, 17)
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))
        wrong = make_pe()
        struct.pack_into("<H", wrong, 0x94, 100)
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(self.save(wrong))

    def test_symbolic_links_are_rejected(self):
        self.save(make_pe())
        link = Path(self.folder.name) / "redirect.exe"
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("Filesystem cannot create symlinks")
        with self.assertRaises(module.PEProbeError):
            module.inspect_pe(link)

    def test_no_file_execution_or_upload_code_paths(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("os.system(", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("read_bytes()", source)
        self.assertIn('"automatic_function_identification": "not_implemented"', source)


if __name__ == "__main__":
    unittest.main()
