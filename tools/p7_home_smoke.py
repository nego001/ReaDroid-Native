#!/usr/bin/env python3
"""Check the native Home composition and real header actions on Android 10/15."""
import re
import time
try:
    from tools import android_ui_smoke as smoke
except ImportError:
    import android_ui_smoke as smoke


def require(nodes, attribute, value):
    matching = [n for n in nodes if n.attrib.get(attribute, "") == value]
    if not matching:
        raise AssertionError(f"Missing visible Home element {attribute}={value!r}")
    return matching[0]


def check():
    smoke.adb("shell", "am", "start", "-W", "-n", smoke.ACTIVITY)
    time.sleep(2)
    smoke.ensure_foreground()
    nodes = smoke.visible_app_hierarchy()
    for title in ("Olá, Desenvolvedor", "Projetos recentes", "Ações rápidas"):
        require(nodes, "text", title)
    for action in ("Abrir APK", "Analisar", "Build APK",
                   "Decompilar", "Editar Smali", "Assinar APK"):
        require(nodes, "content-desc", action)
    menu = require(nodes, "content-desc", "Abrir menu de navegação")
    gear = require(nodes, "content-desc", "Abrir personalização")
    # Verify both reference icons are in the first viewport, not scrolled away.
    for control in (menu, gear):
        bounds = control.attrib.get("bounds", "")
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
        assert match, "Missing real screen bounds for header control"
        assert int(match.group(2)) < 250, "Header no longer appears near the top"
    smoke.tap(menu)
    dialog = smoke.visible_app_hierarchy()
    require(dialog, "text", "NegrecoDroid")
    require(dialog, "text", "Design Studio")
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.tap(require(smoke.visible_app_hierarchy(), "content-desc",
                      "Abrir personalização"))
    smoke.ensure_foreground()
    require(smoke.visible_app_hierarchy(), "text", "Design Studio")
    # A Smali editor does not exist yet. The quick action must explain its
    # actual capabilities before offering navigation to ordinary APK files.
    smoke.tap(smoke.find_tab(smoke.visible_app_hierarchy(), "Início"))
    smoke.ensure_foreground()
    smali = require(smoke.visible_app_hierarchy(), "content-desc", "Editar Smali")
    smoke.tap(smali)
    dialog = smoke.visible_app_hierarchy()
    require(dialog, "text", "Edição Smali indisponível")
    assert any("não modifica código Smali" in n.attrib.get("text", "")
               for n in dialog), "Smali shortcut misrepresents edit support"
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    selected = smoke.find_tab(smoke.visible_app_hierarchy(), "Início")
    assert "selecionada" in selected.attrib.get("content-desc", ""), (
        "Closing Smali explanation must not unexpectedly navigate")
    print("P7_HOME_PASS: header, six actions, real menu, Design settings "
          "and truthful Smali capability", flush=True)


if __name__ == "__main__":
    check()
