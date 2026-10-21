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
    # Tiles must apply a real catalog choice via confirmation, not merely
    # move a decorative selection check. Back must undo the pending highlight.
    before = smoke.visible_app_hierarchy()
    selected = [n.attrib.get("content-desc", "") for n in before
                if ", prévia selecionada" in n.attrib.get("content-desc", "")
                and n.attrib.get("content-desc", "").startswith(
                    ("Negreco Blue", "Carbon Dark", "Matrix Green", "Sunset"))]
    assert len(selected) == 1, "A saved theme must be reflected in its preview"
    theme = "Matrix Green" if not selected[0].startswith("Matrix Green") else "Negreco Blue"
    tile = next((n for n in before if n.attrib.get("content-desc") ==
                 theme + ", selecionar prévia"), None)
    assert tile is not None, "Unselected preview is not an interactive tile"
    smoke.tap(tile)
    modal = {n.attrib.get("text", "") for n in smoke.visible_app_hierarchy()}
    assert "Aplicar " + theme + "?" in modal, (
        "Theme preview did not open a real confirmation")
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    after = smoke.visible_app_hierarchy()
    assert any(n.attrib.get("content-desc") == selected[0] for n in after), (
        "Android Back must restore the previously applied theme")
    # Icon creation must be an operational editor, not the old placeholder.
    icon_tabs = [n for n in after if n.attrib.get("text") == "Ícones"
                 and n.attrib.get("clickable") == "true"]
    assert len(icon_tabs) == 1, "Design Studio Icons tab missing"
    smoke.tap(icon_tabs[0])
    icon_nodes = smoke.visible_app_hierarchy()
    actions = [n for n in icon_nodes
               if n.attrib.get("text", "").startswith(
                   "Abrir criador de ícones  ↗")
               and n.attrib.get("clickable") == "true"]
    assert len(actions) == 1, "Native icon creator entry missing"
    smoke.tap(actions[0])
    workshop = smoke.visible_app_hierarchy()
    workshop_texts = {n.attrib.get("text", "") for n in workshop}
    for expected in ("Criador de Ícones", "Cor", "Símbolo",
                     "Formato", "Exportar PNG"):
        assert expected in workshop_texts, (
            "Native icon workshop missing real control " + expected)
    assert any(n.attrib.get("content-desc") == "Prévia original do ícone"
               for n in workshop), "Native Canvas icon preview not displayed"
    # Cancel, don't create an APK or write a PNG during CI smoke.
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    logo_nodes = smoke.visible_app_hierarchy()
    logo_tabs = [n for n in logo_nodes if n.attrib.get("text") == "Logotipo"
                 and n.attrib.get("clickable") == "true"]
    assert len(logo_tabs) == 1, "Logo Studio tab missing"
    smoke.tap(logo_tabs[0])
    logo_page = smoke.visible_app_hierarchy()
    assert any(n.attrib.get("content-desc") ==
               "Prévia da identidade visual atual"
               for n in logo_page), "Real saved-brand preview missing"
    print(f"P7_DESIGN_PASS api={api} screenshot={target} "
          "apply_cancel=ok icon_workshop=ok saved_logo=ok", flush=True)


if __name__ == "__main__":
    check()
