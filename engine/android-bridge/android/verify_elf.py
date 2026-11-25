"""Structural verification for freshly built, trusted laboratory ELF outputs."""
import hashlib
import pathlib
import re
import struct
import subprocess
import sys

path = pathlib.Path(sys.argv[1])
machine = int(sys.argv[2])
readelf, nm = sys.argv[3:]
data = path.read_bytes()
assert 64 <= len(data) <= 32 * 1024 * 1024
assert data[:7] == b"\x7fELF\x02\x01\x01", "ELF64 little-endian"
header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
_, kind, actual_machine, version, _, phoff, _, _, ehsize, phentsize, phnum, *_ = header
assert (kind, actual_machine, version, ehsize, phentsize) == (3, machine, 1, 64, 56)
assert 0 < phnum <= 128 and phoff + phnum * phentsize <= len(data)
loads = 0
stack = False
dynamic = False
relro = False
for i in range(phnum):
    typ, flags, offset, vaddr, _, filesz, memsz, align = struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize)
    if typ == 1:
        loads += 1
        assert align >= 16384 and align & (align - 1) == 0
        assert offset % align == vaddr % align
        assert filesz <= memsz and offset + filesz <= len(data)
        assert flags & 3 != 3, "writable and executable segment"
    elif typ == 2:
        dynamic = True
    elif typ == 0x6474E551:
        stack = True
        assert flags & 1 == 0, "executable stack"
    elif typ == 0x6474E552:
        relro = True
assert loads >= 2 and stack and dynamic and relro
dyn = subprocess.check_output([readelf, "-d", str(path)], text=True)
needed = set(re.findall(r"\(NEEDED\).*?\[(.*?)\]", dyn))
assert "libc.so" in needed
assert needed <= {"libc.so", "libdl.so", "libm.so", "liblog.so", "libandroid.so", "libunwind.so"}, needed
assert re.search(r"\(SONAME\).*?\[libnegrodroid_hex\.so\]", dyn)
assert "TEXTREL" not in dyn and "RPATH" not in dyn and "RUNPATH" not in dyn
assert "BIND_NOW" in dyn or re.search(r"\(FLAGS_1\).*?\bNOW\b", dyn)
symbols = subprocess.check_output([nm, "--dynamic", "--defined-only", "--extern-only", "--format=posix", str(path)], text=True)
actual = {line.split()[0] for line in symbols.splitlines() if line.strip()}
expected = {"Java_com_readroid_app_NativeHexBridge_abiVersion", "Java_com_readroid_app_NativeHexBridge_format"}
assert actual == expected, actual
print("U2_3_ELF_CONTRACT_PASS", path.parent.name, "machine", machine, "loads", loads, "bytes", len(data), "sha256", hashlib.sha256(data).hexdigest(), "needed", sorted(needed))
