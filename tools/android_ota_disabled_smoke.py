#!/usr/bin/env python3
"""Proves that OTA verification stays blocked in the actual Android UI.

Run only on disposable emulator after installing the current debug APK.
No network request, download or installation should be triggered.
"""
import subprocess
import time
from android_ui_smoke import adb, ensure_foreground, hierarchy, tap
from android_project_smoke import inspect, match_node, click_named, snapshot


def find_visible(text, attempts=12):
    for attempt in range(attempts):
        nodes = hierarchy()
        for node in nodes:
            if text.casefold() in node.attrib.get("text", "").casefold():
                bounds = node.attrib.get("bounds", "")
                # Do not tap a view outside the visible section of the screen.
                import re
                match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if match:
                    x1, y1, x2, y2 = map(int, match.groups())
                    if x2 > x1 and 0 < y1 < y2 <= 640:
                        return node
        adb("shell", "input", "swipe", "160", "510", "160", "170", "350")
        time.sleep(.65)
    inspect("Missing OTA UI action")
    raise AssertionError("Visible OTA control not found: " + text)


def confirm_blocked(channel):
    tap(find_visible("Verificar atualizações"))
    nodes = inspect("OTA blocked " + channel)
    if match_node(nodes, text="OTA assinada ainda não configurada") is None:
        raise AssertionError(channel + " channel unexpectedly offered a download")
    if not any("nenhum APK será baixado automaticamente" in n.attrib.get("text", "")
               for n in nodes):
        raise AssertionError("The blocked OTA notice does not explain the no-download policy")
    snapshot("v3-ota-blocked-" + channel + ".png")
    click_named(text="FECHAR")


def main():
    adb("shell", "am", "start", "-W", "-n", "com.readroid.app/.MainActivity")
    time.sleep(2)
    ensure_foreground()
    confirm_blocked("stable")
    tap(find_visible("Selecionar canal OTA"))
    nodes = inspect("OTA channel options")
    if match_node(nodes, text="Beta") is None:
        raise AssertionError("Beta channel is not selectable")
    click_named(text="Beta")
    nodes = hierarchy()
    if not any("Canal: Beta" in n.attrib.get("text", "") for n in nodes):
        inspect("Missing beta status")
        raise AssertionError("OTA beta preference not reflected in UI")
    confirm_blocked("beta")
    ensure_foreground()
    print("PASS: stable and beta OTA buttons stay blocked without pins, no download offered")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            with open("v3-ota-android-runtime.txt", "w", encoding="utf-8") as log:
                log.write(adb("logcat", "-d", "-s", "AndroidRuntime:E"))
        except (OSError, subprocess.SubprocessError) as error:
            print("Cannot collect logcat:", error)
