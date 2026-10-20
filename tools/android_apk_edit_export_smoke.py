#!/usr/bin/env python3
"""Real Android SAF flow: open APK -> edit text -> review -> export unsigned ZIP.

Disposable emulator only. Does not sign/install modified APKs and never accesses
user-owned apps. Uses a fixture made from the CI-built NegrescoDroid debug APK.
"""
import hashlib
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

from android_project_smoke import (
    PACKAGE, click_named, inspect, match_node, snapshot, wait_project,
)
from android_saf_preset_smoke import picker_downloads
from android_ui_smoke import adb, ensure_foreground, hierarchy, tap

ASSET = "assets/negresco_smoke.txt"
ORIGINAL = "Negresco V3 original"
SUFFIX = "_EDITADO"
INPUT_APK = "NegrescoEditSmoke.apk"
OUTPUT_APK = "negrescodroid-modificado-unsigned.apk"
LOCAL_FIXTURE = Path("v3-edit-source.apk")
LOCAL_EXPORT = Path("v3-edit-output-unsigned.apk")
DEVICE_FIXTURE = "/sdcard/Download/" + INPUT_APK
DEVICE_EXPORT = "/sdcard/Download/" + OUTPUT_APK


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build_fixture():
    source = Path("app/build/outputs/apk/debug/app-debug.apk")
    assert source.is_file(), "Missing Android debug APK build"
    with zipfile.ZipFile(source) as archive:
        if ASSET in archive.namelist():
            raise AssertionError("Fixture asset already exists")
        with zipfile.ZipFile(LOCAL_FIXTURE, "w", compression=zipfile.ZIP_DEFLATED) as result:
            for item in archive.infolist():
                result.writestr(item, archive.read(item.filename))
            result.writestr(ASSET, ORIGINAL.encode("utf-8"))
    with zipfile.ZipFile(LOCAL_FIXTURE) as archive:
        assert archive.read(ASSET).decode("utf-8") == ORIGINAL
        assert archive.getinfo("classes.dex").file_size > 0
    return sha256(LOCAL_FIXTURE.read_bytes())


def wait_for_node(prefix, timeout=35):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        nodes = hierarchy()
        for node in nodes:
            text = node.attrib.get("text", "")
            if prefix.casefold() in text.casefold():
                return node
        time.sleep(1)
    inspect("Node not found: " + prefix)
    raise AssertionError("No Android UI node containing " + prefix)


def click_text(prefix, timeout=30):
    node = wait_for_node(prefix, timeout=timeout)
    tap(node)


def open_fixture():
    adb("push", str(LOCAL_FIXTURE), DEVICE_FIXTURE)
    adb("shell", "am", "broadcast", "-a",
        "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", "file://" + DEVICE_FIXTURE)
    adb("shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
    time.sleep(2)
    click_named(desc="Selecionar arquivo APK para analisar")
    time.sleep(2)
    nodes = hierarchy()
    if match_node(nodes, text=INPUT_APK) is None:
        picker_downloads()
    click_text(INPUT_APK)
    wait_project()
    ensure_foreground()
    snapshot("v3-edit-01-project.png")


def edit_asset():
    click_named(desc="Seção Arquivos", partial=True)
    nodes = inspect("Files tab after loading fixture")
    if match_node(nodes, text="assets/", partial=True) is None:
        # Locate by search when the folder is below the fold.
        searches = [n for n in nodes if n.attrib.get("class") == "android.widget.EditText"]
        if not searches:
            raise AssertionError("File search input not present")
        tap(searches[0])
        adb("shell", "input", "text", "negresco_smoke")
        time.sleep(1)
    else:
        click_text("assets/")
    click_text("negresco_smoke.txt")
    nodes = inspect("File action dialog")
    click_text("PLANEJAR EDIÇÃO")
    wait_for_node("Planejar alteração: " + ASSET, timeout=25)
    editors = [n for n in hierarchy() if n.attrib.get("class") == "android.widget.EditText"]
    if not editors:
        raise AssertionError("No native text editor dialog")
    editor = editors[-1]
    tap(editor)
    adb("shell", "input", "keyevent", "123")  # Android KEYCODE_MOVE_END
    adb("shell", "input", "text", SUFFIX)
    time.sleep(1)
    editors = [n for n in hierarchy() if n.attrib.get("class") == "android.widget.EditText"]
    if not any((ORIGINAL + SUFFIX) in n.attrib.get("text", "") for n in editors):
        inspect("Editor did not append expected text")
        raise AssertionError("Text editor did not contain expected replacement")
    click_text("SALVAR NO PLANO")
    click_text("OK")
    nodes = inspect("Saved edit plan")
    if not any("1 alterações pendentes" in n.attrib.get("text", "") for n in nodes):
        raise AssertionError("Edit plan was not updated")
    snapshot("v3-edit-02-plan.png")


def review_and_export(source_sha):
    click_named(desc="Seção Construir", partial=True)
    click_text("Revisar alterações pendentes")
    nodes = inspect("Review edit plan")
    if match_node(nodes, text=ASSET, partial=True) is None:
        raise AssertionError("Modified text path missing from review")
    click_text("FECHAR")
    click_text("Exportar APK modificado")
    nodes = inspect("Unsigned export disclosure")
    if match_node(nodes, text="Reconstrução experimental") is None:
        raise AssertionError("Missing explicit unsigned export warning")
    click_text("ESCOLHER DESTINO")
    picker_downloads()
    nodes = inspect("SAF APK export destination")
    if match_node(nodes, text=OUTPUT_APK, partial=True) is None:
        raise AssertionError("Default unsigned filename was not supplied")
    click_text("SAVE")
    wait_for_node("Exportação verificada", timeout=45)
    nodes = hierarchy()
    if not any("verificado por SHA-256" in n.attrib.get("text", "") for n in nodes):
        inspect("No export SHA verification")
        raise AssertionError("App did not confirm checksum verified SAF export")
    if not any("NÃO está assinado" in n.attrib.get("text", "") for n in nodes):
        raise AssertionError("Missing unsigned APK warning")
    snapshot("v3-edit-03-export-verified.png")
    click_text("DETALHES TÉCNICOS")
    nodes = inspect("Technical export report")
    if not any("Pré-verificação estrutural aprovada" in n.attrib.get("text", "")
               for n in nodes):
        raise AssertionError("Technical verification report is missing")
    technical_text = "\n".join(n.attrib.get("text", "") for n in nodes)
    assert "SHA-256 da origem (antes e depois)" in technical_text, (
        "The original input checksum was not disclosed in export details"
    )
    assert source_sha in technical_text, (
        "Export's original SHA-256 differs from the known test fixture"
    )
    match = re.search(
        r"SHA-256 do APK reconstruído e exportado:\s*([0-9a-f]{64})",
        technical_text,
    )
    assert match, "Rebuilt APK SHA-256 missing from technical evidence"
    assert "arquivo(s) não editado(s) conferido(s)" in technical_text, (
        "Full unchanged-entry verification missing from export details"
    )
    snapshot("v3-edit-04-export-details.png")
    click_text("FECHAR")
    return match.group(1)


def check_export(source_sha, output_sha):
    # SAF's Downloads provider on API29 stores the created file in shared Downloads.
    subprocess.check_call(["adb", "pull", DEVICE_EXPORT, str(LOCAL_EXPORT)], timeout=60)
    assert LOCAL_EXPORT.stat().st_size > 0, "Empty exported APK"
    assert sha256(LOCAL_EXPORT.read_bytes()) == output_sha, (
        "Exported APK bytes do not match the checksum shown to the user"
    )
    with zipfile.ZipFile(LOCAL_FIXTURE) as original, zipfile.ZipFile(LOCAL_EXPORT) as changed:
        assert original.read(ASSET).decode("utf-8") == ORIGINAL
        assert changed.read(ASSET).decode("utf-8") == ORIGINAL + SUFFIX
        originals = set(original.namelist())
        rebuilt = set(changed.namelist())
        expected = set()
        for name in originals:
            upper = name.upper()
            if upper.startswith("META-INF/") and (upper.endswith((".RSA", ".DSA", ".EC", ".SF"))
                    or upper == "META-INF/MANIFEST.MF"):
                assert name not in rebuilt, "Old signature metadata remained: " + name
            else:
                expected.add(name)
                assert name in rebuilt, "Missing entry: " + name
                if name != ASSET:
                    assert sha256(original.read(name)) == sha256(changed.read(name)), (
                        "Untouched entry changed without approval: " + name
                    )
        assert rebuilt == expected, (
            "Rebuilt ZIP has entries outside the original minus removed signatures"
        )
    assert sha256(LOCAL_FIXTURE.read_bytes()) == source_sha, "Original fixture changed"
    device = adb("shell", "sha256sum", DEVICE_FIXTURE).split()[0]
    assert device == source_sha, "Original APK on Android was modified"
    print("PASS: SAF edit and SHA-verified export, exact replacement, "
          "all untouched entries, source integrity and signature metadata removal")


def main():
    old_hash = build_fixture()
    open_fixture()
    edit_asset()
    output_hash = review_and_export(old_hash)
    check_export(old_hash, output_hash)


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            snapshot("v3-edit-final.png")
            inspect("Final UI state")
        except (OSError, subprocess.SubprocessError) as error:
            print("Final diagnostics unavailable:", error)
        try:
            with open("v3-edit-android-runtime.txt", "w", encoding="utf-8") as log:
                log.write(adb("logcat", "-d", "-s", "AndroidRuntime:E"))
        except (OSError, subprocess.SubprocessError):
            pass
