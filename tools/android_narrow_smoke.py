#!/usr/bin/env python3
"""Real narrow-screen navigation check with Android font scale set to 130%.

The workflow uses a disposable API 29 emulator resized to 320x640dp.
"""
import re
import subprocess
import time

from android_ui_smoke import adb, ensure_foreground, find_tab, hierarchy, tap

TABS = ("Início", "Arquivos", "Construir", "Segurança", "IA")


def rectangle(node):
    raw = node.attrib.get("bounds", "")
    result = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", raw)
    if not result:
        raise AssertionError("Missing Android UI node bounds: " + raw)
    return tuple(map(int, result.groups()))


def capture(name):
    with open(name, "wb") as output:
        output.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))


def assert_navigation():
    nodes = hierarchy()
    screen_width = 320
    for name in TABS:
        node = find_tab(nodes, name)
        x1, y1, x2, y2 = rectangle(node)
        if not (0 <= x1 < x2 <= screen_width and 0 <= y1 < y2 <= 640):
            raise AssertionError(f"Tab {name!r} is outside 320x640 screen: {x1,y1,x2,y2}")
        if x2-x1 < 32 or y2-y1 < 44:
            raise AssertionError(f"Tab {name!r} has an undersized tap target")
    return nodes


def main():
    dims = adb("shell", "wm", "size")
    density = adb("shell", "wm", "density")
    print("Narrow device:", dims, density, flush=True)
    if "320x640" not in dims:
        raise AssertionError("Emulator did not switch to 320x640 resolution")
    adb("shell", "am", "start", "-W", "-n", "com.readroid.app/.MainActivity")
    time.sleep(3)
    ensure_foreground()
    assert_navigation()
    capture("v3-studio-narrow-home.png")
    for name in TABS[1:]:
        tap(find_tab(hierarchy(), name))
        selected = find_tab(assert_navigation(), name)
        if "selecionada" not in selected.attrib.get("content-desc", ""):
            raise AssertionError(f"{name} is not visibly selected")
        ensure_foreground()
        if name == "Arquivos":
            capture("v3-studio-narrow-files.png")
    tap(find_tab(hierarchy(), "Início"))
    ensure_foreground()
    capture("v3-studio-narrow-return.png")
    print("PASS: all five tabs visible and functional in 320dp viewport at Android font scale 130%")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            capture("v3-studio-narrow-final.png")
        except subprocess.SubprocessError as error:
            print("Could not capture final screenshot:", error)
