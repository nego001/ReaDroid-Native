"""Compare Rust output byte for byte with the unchanged Java F2.2 formatter."""
from pathlib import Path
import subprocess
import tempfile
import hashlib

CORE=Path(__file__).resolve().parents[1]
ROOT=CORE.parents[1]
JAVA=ROOT/"app/src/main/java/com/readroid/app/ApkHexPreview.java"
FIXTURE=CORE/"tests/java/HexParityFixture.java"
with tempfile.TemporaryDirectory() as output:
    subprocess.run(["javac","-encoding","UTF-8","-d",output,str(JAVA),str(FIXTURE)],check=True)
    for mode in ("empty","single","boundary","all","max"):
        j=subprocess.check_output(["java","-cp",output,"com.readroid.app.HexParityFixture",mode])
        r=subprocess.check_output(["cargo","+1.85.1","run","--quiet","--locked","--offline","--example","hex_fixture","--",mode],cwd=CORE)
        assert r==j, ("hex parity mismatch",mode,len(j),len(r))
        print("F2_2_HEX_PARITY_PASS",mode,len(r),hashlib.sha256(r).hexdigest())
print("U2_1_HOST_HEX_PARITY_PASS",5)
