#!/usr/bin/env python3
"""Smoke and screenshot of the real Design Studio on Android 10/15.

No user APK or saved project is required for this visual regression capture.
"""
import subprocess
import time
try:
    from tools import android_ui_smoke as smoke
except ImportError:
    import android_ui_smoke as smoke


def check():
    smoke.adb("shell", "am", "start", "-W", "-n", smoke.ACTIVITY)
    time.sleep(2)
    smoke.ensure_foreground()
    smoke.tap(smoke.find_tab(smoke.visible_app_hierarchy(), "Design"))
    smoke.ensure_foreground()
    nodes = smoke.visible_app_hierarchy()
    current = smoke.find_tab(nodes, "Design")
    assert "selecionada" in current.attrib.get("content-desc", ""), (
        "Design tab not selected")
    labels = {n.attrib.get("text", "") for n in nodes}
    # The approved reference shows all these groups in the first viewport.
    # Do not count a long scroll containing them as a 1:1 success.
    for needed in ("Design Studio", "Previews de Temas", "Opções de Layout",
                   "Presets de Aparência", "Criador de Ícones", "Logo Studio",
                   "Temas", "Layout", "Ícones", "Logotipo", "Dark OLED"):
        if needed not in labels:
            raise AssertionError("Missing Design Studio element: " + needed)
    dialogs = [n for n in nodes if n.attrib.get("content-desc", "") ==
               "Ver todos: Previews de Temas"]
    assert len(dialogs) == 1, "Reference catalog action missing"
    api = smoke.adb("shell", "getprop", "ro.build.version.sdk").strip()
    if api not in ("29", "35"):
        raise AssertionError("Unexpected Android SDK level: " + api)
    target = f"p7-design-android-{api}.png"
    with open(target, "wb") as stream:
        stream.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    # "Ver todos" must actually open the native catalog, not be decorative.
    smoke.tap(dialogs[0])
    opened = {n.attrib.get("text", "") for n in smoke.visible_app_hierarchy()}
    assert "Temas disponíveis" in opened, "Theme catalog dialog did not open"
    assert "Carbon Dark" in opened, "Theme catalog options not loaded"
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    print(f"P7_DESIGN_PASS api={api} screenshot={target}", flush=True)


if __name__ == "__main__":
    check()
