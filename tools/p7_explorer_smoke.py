#!/usr/bin/env python3
"""Read-only screenshot smoke of P7 Explorer on Android emulator.

Only uses the installed synthetic QA/debug application, opens no user APK.
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
    smoke.tap(smoke.find_tab(smoke.visible_app_hierarchy(), "Arquivos"))
    smoke.ensure_foreground()
    nodes = smoke.visible_app_hierarchy()
    selected = smoke.find_tab(nodes, "Arquivos")
    assert "selecionada" in selected.attrib.get("content-desc", ""), "Files tab not selected"
    labels = {n.attrib.get("text", "") for n in nodes}
    assert "Explorador de Arquivos" in labels, "P7 Explorer header missing"
    assert "Nenhum APK selecionado" in labels, "Unloaded state missing"
    assert "Todos" in labels, "Quick filter bar missing"
    assert any(n.attrib.get("content-desc", "").startswith("Ir à raiz do APK")
               for n in nodes), "Interactive breadcrumb root missing"
    api = smoke.adb("shell", "getprop", "ro.build.version.sdk").strip()
    if api not in ("29", "35"):
        raise AssertionError("Unexpected emulator API: " + api)
    path = f"p7-explorer-android-{api}.png"
    with open(path, "wb") as out:
        out.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    print(f"P7_EXPLORER_PASS api={api} screenshot={path}", flush=True)


if __name__ == "__main__":
    check()
