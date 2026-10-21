#!/usr/bin/env python3
"""P7 large-text QA: actual Android UI at 200% font scale, original viewport.

Use after compact 320dp/130% smoke. Never import/export APKs or change
display resolution; restore the device font setting even on assertions.
"""
import re
import subprocess

try:
    from tools import android_ui_smoke as smoke
    from tools.p7_compact_smoke import (
        launch, parse_wm, require_accessible_target)
except ImportError:
    import android_ui_smoke as smoke
    from p7_compact_smoke import launch, parse_wm, require_accessible_target

HEADINGS = (
    ("Início", "Olá, Desenvolvedor"),
    ("Arquivos", "Explorador de Arquivos"),
    ("Design", "Design Studio"),
)
REQUIRED_TARGETS = {
    "Início": ("Abrir menu de navegação", "Abrir personalização",
               "Ver todos os projetos recentes"),
    "Arquivos": ("Ir à raiz do APK", "Abrir plano de edição"),
    "Design": ("Temas, aba selecionada", "Layout, selecionar aba",
               "Ver todos: Previews de Temas"),
}


def check_screen(section, heading, viewport, density, api):
    smoke.tap(smoke.find_tab(smoke.visible_app_hierarchy(), section))
    smoke.ensure_foreground()
    nodes = smoke.visible_app_hierarchy()
    selected = smoke.find_tab(nodes, section).attrib.get("content-desc", "")
    if "selecionada" not in selected:
        raise AssertionError(f"{section}: tab not selected at 200% font scale")
    if not any(n.attrib.get("text") == heading for n in nodes):
        raise AssertionError(f"{section}: essential heading missing at 200%")
    # All five navigation items must remain reachable in the viewport.
    width, height = viewport
    for name in ("Início", "Arquivos", "Segurança", "Build", "Design"):
        target = smoke.find_tab(nodes, name)
        bounds = target.attrib.get("bounds", "")
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
        if not match:
            raise AssertionError(f"{name}: navigation bounds unavailable")
        x1, y1, x2, y2 = map(int, match.groups())
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise AssertionError(f"{name}: navigation clipped at 200%: {bounds}")
    for description in REQUIRED_TARGETS[section]:
        require_accessible_target(nodes, description, density, viewport)
    filename = f"p7-large-text-{section.lower().replace('í', 'i')}-android-{api}.png"
    with open(filename, "wb") as screenshot:
        screenshot.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    print(f"P7_LARGE_TEXT_SCREEN_PASS api={api} section={section} font=200% "
          f"targets={len(REQUIRED_TARGETS[section])} screenshot={filename}",
          flush=True)


def check():
    api = smoke.adb("shell", "getprop", "ro.build.version.sdk").strip()
    if api not in ("29", "35"):
        raise AssertionError(f"Unsupported test emulator API: {api}")
    viewport, _ = parse_wm(smoke.adb("shell", "wm", "size"), "size")
    (density_info, _) = parse_wm(
        smoke.adb("shell", "wm", "density"), "density")
    density = density_info[0]
    prior = smoke.adb("shell", "settings", "get", "system", "font_scale")
    print(f"P7_LARGE_TEXT_START api={api} viewport={viewport} "
          f"density={density} prior_font={prior}", flush=True)
    try:
        smoke.adb("shell", "settings", "put", "system", "font_scale", "2.0")
        launch()
        for section, heading in HEADINGS:
            check_screen(section, heading, viewport, density, api)
        print(f"P7_LARGE_TEXT_PASS api={api} font=200%", flush=True)
    finally:
        if prior in ("", "null"):
            smoke.adb("shell", "settings", "delete", "system", "font_scale")
        else:
            smoke.adb("shell", "settings", "put", "system", "font_scale",
                      prior)
        launch()
        print(f"P7_LARGE_TEXT_RESTORED api={api}", flush=True)


if __name__ == "__main__":
    check()
