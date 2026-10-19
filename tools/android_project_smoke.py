#!/usr/bin/env python3
"""End-to-end SAF / project / theme smoke on a disposable Android emulator.

Only uses a locally built NegrescoDroid APK as test input. This test must never
be pointed at a real user device or private APKs.
"""
import subprocess
import time

from android_ui_smoke import adb, ensure_foreground, hierarchy, tap, find_tab

PACKAGE = "com.readroid.app"
FIXTURE = "/sdcard/Download/NegrescoDroid-Smoke.apk"
LOCAL_APK = "app/build/outputs/apk/debug/app-debug.apk"


def snapshot(name):
    with open(name, "wb") as target:
        target.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))


def match_node(nodes, *, text=None, desc=None, partial=False):
    for node in nodes:
        t = node.attrib.get("text", "")
        d = node.attrib.get("content-desc", "")
        if text is not None and ((text in t) if partial else text == t):
            return node
        if desc is not None and ((desc in d) if partial else desc == d):
            return node
    return None


def inspect(stage):
    nodes = hierarchy()
    print(stage, "nodes:", [
        (node.attrib.get("text", "")[:70], node.attrib.get("content-desc", "")[:70])
        for node in nodes if node.attrib.get("text") or node.attrib.get("content-desc")
    ], flush=True)
    return nodes


def click_named(*, text=None, desc=None, partial=False, timeout=10):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        nodes = hierarchy()
        node = match_node(nodes, text=text, desc=desc, partial=partial)
        if node is not None:
            tap(node)
            return
        time.sleep(1)
    raise AssertionError(f"UI control not found: text={text}, desc={desc}")


def pick_fixture():
    adb("push", LOCAL_APK, FIXTURE)
    adb("shell", "am", "broadcast", "-a",
        "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d", "file://" + FIXTURE)
    adb("shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
    time.sleep(2)
    ensure_foreground()
    click_named(desc="Selecionar arquivo APK para analisar")
    time.sleep(3)
    nodes = inspect("Document picker initial")
    if match_node(nodes, text="NegrescoDroid-Smoke", partial=True) is not None:
        click_named(text="NegrescoDroid-Smoke", partial=True)
        return
    # DocumentsUI may begin in Recents. Open the drawer and enter Downloads.
    drawer = (match_node(nodes, desc="Show roots")
              or match_node(nodes, desc="Show navigation drawer")
              or match_node(nodes, desc="Navigate up"))
    if drawer is not None:
        tap(drawer)
    else:
        adb("shell", "input", "tap", "35", "110")
        time.sleep(1)
    nodes = inspect("Document picker drawer")
    downloads = (match_node(nodes, text="Downloads")
                 or match_node(nodes, text="Download")
                 or match_node(nodes, desc="Downloads")
                 or match_node(nodes, desc="Download"))
    if downloads is None:
        raise AssertionError("Downloads entry not found in DocumentsUI picker")
    tap(downloads)
    nodes = inspect("Document picker downloads")
    if match_node(nodes, text="NegrescoDroid-Smoke", partial=True) is None:
        raise AssertionError("Smoke APK is absent from DocumentsUI Downloads")
    click_named(text="NegrescoDroid-Smoke", partial=True)


def wait_project():
    until = time.monotonic() + 35
    while time.monotonic() < until:
        nodes = hierarchy()
        for node in nodes:
            if PACKAGE in node.attrib.get("text", ""):
                ensure_foreground()
                return
        if match_node(nodes, text="FALHA AO ABRIR PROJETO"):
            raise AssertionError("Project analysis failed")
        time.sleep(2)
    inspect("No analyzed project")
    raise AssertionError("Timed out waiting for analyzed APK metadata")


def find_and_tap_setting(prefix):
    # Scroll only inside the actual Home section; never interact with unseen cards.
    click_named(desc="Seção Início", partial=True)
    for _ in range(9):
        nodes = hierarchy()
        # Settings are collapsed on first install to keep Home uncluttered.
        toggle = match_node(nodes, text="Opções de aparência", partial=True)
        if toggle is not None and "▾" in toggle.attrib.get("text", ""):
            tap(toggle)
            nodes = hierarchy()
        item = match_node(nodes, desc=prefix, partial=True)
        if item is not None:
            bounds = item.attrib.get("bounds", "")
            # The accessibility hierarchy may include offscreen items.
            import re
            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
            if m and 80 < int(m.group(2)) < 1750:
                tap(item)
                return
        adb("shell", "input", "swipe", "470", "1570", "470", "680", "400")
        time.sleep(1)
    inspect("Personalization card not found")
    raise AssertionError(f"Cannot reach customization option {prefix}")


def main():
    pick_fixture()
    wait_project()
    snapshot("v3-smoke-project-loaded.png")
    click_named(desc="Seção Arquivos", partial=True)
    nodes = inspect("Explorer with inspected APK")
    if match_node(nodes, text="0 pastas", partial=True):
        raise AssertionError("Explorer displayed no directory entries")
    ensure_foreground()
    click_named(desc="Seção Início", partial=True)
    find_and_tap_setting("Tema visual.")
    inspect("Theme choices")
    click_named(text="Claro")
    wait_project()
    snapshot("v3-smoke-theme-light.png")
    find_and_tap_setting("Tamanho do texto.")
    click_named(text="Muito grande (130%)")
    wait_project()
    snapshot("v3-smoke-font-130.png")
    find_and_tap_setting("Espaçamento da interface.")
    click_named(text="Compacto")
    wait_project()
    snapshot("v3-smoke-compact.png")
    # Verify the real UI wrote the expected preferences without backdoors in the app.
    preferences = adb("shell", "run-as", PACKAGE,
        "cat", "shared_prefs/v3_personalizacao.xml")
    import xml.etree.ElementTree as ET
    root = ET.fromstring(preferences)
    saved = {}
    for node in root:
        name = node.attrib.get("name")
        if name:
            saved[name] = node.attrib.get("value", node.text or "")
    if saved.get("font_percent") != "130":
        raise AssertionError("Font setting was not persisted: " + repr(saved.get("font_percent")))
    if saved.get("compact") != "true":
        raise AssertionError("Compact mode was not persisted: " + repr(saved.get("compact")))
    if saved.get("theme") != "light":
        raise AssertionError("Light theme was not persisted: " + repr(saved.get("theme")))
    ensure_foreground()
    print("PASS: real APK analysis, file exploration, light theme, 130% fonts and compact mode; project retained")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            snapshot("v3-smoke-project-final.png")
        except (OSError, subprocess.SubprocessError) as err:
            print("Cannot capture final screenshot:", err)
        try:
            inspect("Final hierarchy")
        except (OSError, subprocess.SubprocessError) as err:
            print("Cannot capture final hierarchy:", err)
