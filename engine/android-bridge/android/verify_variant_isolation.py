"""Check generated flags and merged native libraries, without QA/release APKs."""
from pathlib import Path
import re
import sys

root=Path(sys.argv[1])
for variant in ("qa","release"):
    configs=list((root/"generated"/"source"/"buildConfig"/variant).rglob("BuildConfig.java"))
    assert len(configs)==1, (variant,configs)
    source=configs[0].read_text(encoding="utf-8")
    assert re.search(r"\bboolean\s+NATIVE_HEX_ENABLED\s*=\s*false\s*;",source), variant
    merged=root/"intermediates"/"merged_native_libs"/variant
    # No libraries may exist for a Java-only variant; AGP can omit empty dirs.
    assert not list(merged.rglob("libnegrodroid_hex.so")), variant
    print("U2_6_VARIANT_ISOLATION_PASS",variant)
