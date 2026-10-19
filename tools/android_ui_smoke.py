#!/usr/bin/env python3
"""Small real-device/emulator smoke: launch app and exercise bottom navigation.

Requires adb and a connected/emulated Android device; never edits user APKs.
"""
import re
import subprocess
import time
import xml.etree.ElementTree as ET


PKG = "com.readroid.app"
ACTIVITY = PKG + "/.MainActivity"


def adb(*args):
    return subprocess.check_output(["adb", *args], text=True, timeout=45).strip()


def hierarchy():
    for attempt in range(5):
        try:
            adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
            raw = adb("exec-out", "cat", "/sdcard/window.xml")
            with open("v3-studio-android-hierarchy.xml", "w", encoding="utf-8") as out:
                out.write(raw)
            root = ET.fromstring(raw)
            return list(root.iter("node"))
        except (subprocess.SubprocessError, ET.ParseError):
            if attempt == 4:
                raise
            time.sleep(2)
    raise RuntimeError("UI hierarchy unavailable")


def find_tab(nodes, name):
    prefix = "Seção " + name
    for node in nodes:
        desc = node.attrib.get("content-desc", "")
        if desc.startswith(prefix):
            return node
    raise AssertionError(f"Tab {name!r} not found")


def tap(node):
    bounds = node.attrib.get("bounds", "")
    found = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not found:
        raise AssertionError(f"Invalid UI bounds: {bounds!r}")
    x1, y1, x2, y2 = map(int, found.groups())
    if x2 <= x1 or y2 <= y1:
        raise AssertionError("Non-positive tap area")
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
    time.sleep(1.5)


def ensure_foreground():
    pid = adb("shell", "pidof", PKG)
    if not pid or not all(item.isdigit() for item in pid.split()):
        raise AssertionError("NegrescoDroid process not running")
    activities = adb("shell", "dumpsys", "activity", "activities")
    if ACTIVITY not in activities:
        raise AssertionError("NegrescoDroid activity not visible in dumpsys")


def main():
    adb("shell", "am", "start", "-W", "-n", ACTIVITY)
    time.sleep(4)
    ensure_foreground()
    nodes = hierarchy()
    if "selecionada" not in find_tab(nodes, "Início").attrib.get("content-desc", ""):
        raise AssertionError("Home is not the active tab")
    tap(find_tab(nodes, "Arquivos"))
    ensure_foreground()
    nodes = hierarchy()
    if "selecionada" not in find_tab(nodes, "Arquivos").attrib.get("content-desc", ""):
        raise AssertionError("Files navigation did not select the Files tab")
    tap(find_tab(nodes, "Segurança"))
    nodes = hierarchy()
    if "selecionada" not in find_tab(nodes, "Segurança").attrib.get("content-desc", ""):
        raise AssertionError("Security navigation did not select the Security tab")
    tap(find_tab(nodes, "Início"))
    ensure_foreground()
    if "selecionada" not in find_tab(hierarchy(), "Início").attrib.get("content-desc", ""):
        raise AssertionError("Failed to return Home")
    runtime = adb("logcat", "-d", "-s", "AndroidRuntime:E")
    if "FATAL EXCEPTION" in runtime and PKG in runtime:
        raise AssertionError("AndroidRuntime crash detected for NegrescoDroid")
    print("PASS: home -> files -> security -> home; no detected app crash")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Keep the screenshot and crash log even if a navigation assertion fails.
        try:
            with open("v3-studio-android-emulator.png", "wb") as image:
                image.write(subprocess.check_output(
                    ["adb", "exec-out", "screencap", "-p"], timeout=45))
        except subprocess.SubprocessError as error:
            print("Screenshot capture failed:", error)
        try:
            runtime = adb("logcat", "-d", "-s", "AndroidRuntime:E")
            with open("v3-studio-android-runtime.txt", "w", encoding="utf-8") as log:
                log.write(runtime)
        except subprocess.SubprocessError as error:
            print("Runtime log capture failed:", error)
