#!/usr/bin/env python3
"""End-to-end appearance export/import through real Android DocumentsUI.

Run only on a disposable Android emulator. Opens a real APK project, exports
the configured appearance to Downloads with SAF ACTION_CREATE_DOCUMENT,
changes the appearance, and reimports the exported file with SAF
ACTION_OPEN_DOCUMENT. All interactions are UI actions, not direct app APIs.
"""
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET

from android_project_smoke import (
    PACKAGE, click_named, find_and_tap_setting, inspect, match_node,
    pick_fixture, snapshot, wait_project)
from android_ui_smoke import adb, ensure_foreground, hierarchy, tap


EXPORTED_FILE = "negrescodroid-v3-visual.json"


def prefs():
    xml = adb("shell", "run-as", PACKAGE,
        "cat", "shared_prefs/v3_personalizacao.xml")
    root = ET.fromstring(xml)
    return {child.attrib["name"]: child.attrib.get("value", child.text or "")
            for child in root if "name" in child.attrib}


def clickable_matching(nodes, names):
    wanted = {name.casefold() for name in names}
    for node in nodes:
        name = node.attrib.get("text", "").strip().casefold()
        description = node.attrib.get("content-desc", "").strip().casefold()
        if name in wanted or description in wanted:
            return node
    return None


def picker_downloads():
    nodes = inspect("SAF picker")
    # DocumentsUI often starts in Downloads. Its filename text field exists
    # even before a file is saved, so detect the folder header instead.
    if match_node(nodes, text="FILES ON DOWNLOADS") is not None:
        return
    if match_node(nodes, text="FILES IN DOWNLOADS") is not None:
        return
    drawer = clickable_matching(nodes,
        ["Show roots", "Show navigation drawer", "Navigate up",
         "Mostrar raízes", "Mostrar navegação", "Navegar para cima"])
    if drawer is not None:
        tap(drawer)
        nodes = inspect("SAF root drawer")
    downloads = clickable_matching(nodes, ["Downloads", "Download", "Transferências"])
    if downloads is not None:
        tap(downloads)
        inspect("SAF Downloads")
        return
    # DocumentsUI on some emulator images has an unlabeled navigation button.
    adb("shell", "input", "tap", "40", "110")
    nodes = inspect("SAF alternate drawer")
    downloads = clickable_matching(nodes, ["Downloads", "Download", "Transferências"])
    if downloads is None:
        raise AssertionError("Downloads location missing in Android DocumentsUI")
    tap(downloads)
    inspect("SAF Downloads")


def tap_save():
    nodes = inspect("SAF Save document")
    save = clickable_matching(nodes, ["SAVE", "Save", "Salvar"])
    if save is None:
        raise AssertionError("SAF save button is not visible")
    tap(save)
    nodes = inspect("SAF export completed")
    # System picker may require an additional overwrite confirmation.
    overwrite = clickable_matching(nodes, ["REPLACE", "Replace", "Substituir"])
    if overwrite is not None:
        tap(overwrite)
    click_named(text="OK", timeout=12)


def verify_export():
    raw = adb("shell", "cat", "/sdcard/Download/" + EXPORTED_FILE)
    manifest = json.loads(raw)
    if manifest.get("schema") != 1:
        raise AssertionError("Wrong exported preset schema")
    if manifest.get("theme") != "light" or manifest.get("accent") != "purple":
        raise AssertionError("Exported preset did not preserve visual changes")
    if "keystore" in raw.lower() or "password" in raw.lower():
        raise AssertionError("Sensitive-looking data in exported appearance preset")
    print("PASS: SAF-exported JSON in Downloads preserves visual configuration")


def import_saved():
    find_and_tap_setting("Tema visual.")
    click_named(text="OLED preto")
    wait_project()
    assert prefs().get("theme") == "oled"
    find_and_tap_setting("Cor de destaque.")
    click_named(text="Azul")
    wait_project()
    assert prefs().get("accent") == "blue"
    find_and_tap_setting("Importar personalização.")
    picker_downloads()
    click_named(text="negrescodroid-v3-visual", partial=True)
    nodes = inspect("SAF import consent")
    if match_node(nodes, text="Prévia da personalização", partial=True) is None:
        raise AssertionError("Validated appearance preview was not shown")
    if match_node(nodes, text="Tema: Claro", partial=True) is None:
        raise AssertionError("Imported appearance preview lacks the saved theme")
    apply_button = clickable_matching(nodes, ["APLICAR VISUAL", "Aplicar visual"])
    if apply_button is None:
        raise AssertionError("Explicit import approval button not found")
    tap(apply_button)
    wait_project()
    current = prefs()
    if current.get("theme") != "light" or current.get("accent") != "purple":
        raise AssertionError("SAF import did not restore the saved appearance")
    ensure_foreground()
    snapshot("v3-saf-imported-light-purple.png")
    print("PASS: SAF import restored theme/light and accent/purple without losing APK")


def main():
    pick_fixture()
    wait_project()
    find_and_tap_setting("Tema visual.")
    click_named(text="Claro")
    wait_project()
    find_and_tap_setting("Cor de destaque.")
    click_named(text="Roxo")
    wait_project()
    assert prefs().get("theme") == "light"
    assert prefs().get("accent") == "purple"
    snapshot("v3-saf-before-export.png")

    find_and_tap_setting("Exportar personalização.")
    picker_downloads()
    tap_save()
    verify_export()
    import_saved()
    print("PASS: complete appearance SAF export/import lifecycle")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            snapshot("v3-saf-final.png")
        except (OSError, subprocess.SubprocessError) as error:
            print("Cannot capture final screen:", error)
        try:
            inspect("SAF final hierarchy")
        except (OSError, subprocess.SubprocessError) as error:
            print("Cannot capture final hierarchy:", error)
        try:
            with open("v3-saf-runtime.txt", "w", encoding="utf-8") as log:
                log.write(adb("logcat", "-d", "-s", "AndroidRuntime:E"))
        except (OSError, subprocess.SubprocessError):
            pass
