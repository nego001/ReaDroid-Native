# Independent EVEX advanced reference audit

This standalone laboratory is not the NegroDroid decoder and does not change
production code, CI gates, or the required Android integration workflow.

Run on a host with Python 3 and GNU x86-64 binutils on PATH:
```sh
python3 engine/core/tools/verify_evex_advanced_reference.py
```

The script generates assembly in a temporary directory, assembles an object,
extracts .text, checks the entire byte stream against explicit encodings,
and counts disassembly rows. It never links or executes the generated object.
The temporary directory is removed on exit.

Verified locally with GNU Binutils 2.44:
```
PASS: 2120 assembly encodings; 2120 disassembly rows; 10062 bytes
broadcast 520; ternary masks 1536; unary masks 64
```

Broadcast covers all signed disp8-scaled displacements for 32/64-bit
elements, plus two out-of-range and two unaligned disp32 cases per width.
Canonical zero displacement has no encoded disp8. KANDW/KORW/KXORW cover
all 8x8x8 operand triples; KNOTW covers all 8x8 pairs, including K0.
These are reference encodings, not tested decoder support. The existing
EVEX Android API35 evidence gate remains required. No merge or release.
