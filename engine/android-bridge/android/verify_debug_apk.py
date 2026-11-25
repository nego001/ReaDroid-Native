"""Verify only the intended debug package has native hex libraries."""
import sys,zipfile
apk=sys.argv[1]
enabled=sys.argv[2]=="true"
with zipfile.ZipFile(apk) as z:
    names=[n for n in z.namelist() if n.endswith("/libnegrodroid_hex.so")]
    expected=["lib/arm64-v8a/libnegrodroid_hex.so","lib/x86_64/libnegrodroid_hex.so"] if enabled else []
    assert sorted(names)==expected,(names,expected)
    for n in names:
        assert z.getinfo(n).file_size>0
print("U2_4_DEBUG_PACKAGE_PASS native="+str(enabled).lower())
