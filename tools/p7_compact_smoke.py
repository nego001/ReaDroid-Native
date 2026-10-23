#!/usr/bin/env python3
"""P7 compact-phone accessibility smoke on Android 10 and Android 15.

Run only after the regular captures: temporarily apply a 320 dp viewport
with 130% system font scale, navigate three real native screens, capture
evidence, then restore the emulator's previous display/font settings.
No APK is imported or exported and no app signing is attempted.
"""
import re
import subprocess
import time

try:
    from tools import android_ui_smoke as smoke
except ImportError:
    import android_ui_smoke as smoke


def parse_wm(output, dimension):
    """Return effective size/density and prior override for exact restoration."""
    if dimension == "size":
        pattern = r"^(Physical|Override) size:\s*(\d+)x(\d+)\s*$"
    elif dimension == "density":
        pattern = r"^(Physical|Override) density:\s*(\d+)\s*$"
    else:
        raise ValueError("Unsupported wm property")
    matches = re.findall(pattern, output, flags=re.MULTILINE)
    physical = next((entry for entry in matches if entry[0] == "Physical"), None)
    override = next((entry for entry in matches if entry[0] == "Override"), None)
    if not physical:
        raise AssertionError("Physical Android display info unavailable")
    effective = override if override else physical
    values = tuple(int(number) for number in effective[1:])
    previous_override = (tuple(int(number) for number in override[1:])
                         if override else None)
    return values, previous_override


def viewport_pixels(dp_width, dp_height, density):
    if density <= 0:
        raise AssertionError("Invalid Android density")
    return (round(dp_width * density / 160),
            round(dp_height * density / 160))


def launch():
    smoke.adb("shell", "am", "force-stop", smoke.PKG)
    smoke.adb("shell", "am", "start", "-W", "-n", smoke.ACTIVITY)
    time.sleep(3)
    smoke.ensure_foreground()


def require_accessible_target(nodes, description, density, viewport):
    """Fail if a visible, clickable UI node misses the 48dp touch contract."""
    controls = [node for node in nodes
                if node.attrib.get("content-desc") == description
                and node.attrib.get("clickable") == "true"]
    if len(controls) != 1:
        raise AssertionError(
            f"Expected one accessible clickable target {description!r}; "
            f"found {len(controls)}")
    bounds = controls[0].attrib.get("bounds", "")
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        raise AssertionError(f"Missing target bounds for {description}: {bounds!r}")
    x1, y1, x2, y2 = map(int, match.groups())
    width_px, height_px = viewport
    if not (0 <= x1 < x2 <= width_px and 0 <= y1 < y2 <= height_px):
        raise AssertionError(
            f"Target {description} clipped outside viewport: {bounds}")
    minimum = (48 * density + 159) // 160  # ceil(48dp at current display density)
    if x2 - x1 < minimum or y2 - y1 < minimum:
        raise AssertionError(
            f"Target {description} below 48dp: {x2-x1}x{y2-y1} px; "
            f"required {minimum}px at density {density}")


def require_stacked_explorer_summary(nodes):
    """At 320dp the full project name must sit ABOVE the real edit-plan chip."""
    names = [node for node in nodes
             if node.attrib.get("text") == "Nenhum APK selecionado"]
    actions = [node for node in nodes
               if node.attrib.get("content-desc") == "Abrir plano de edição"]
    if len(names) != 1 or len(actions) != 1:
        raise AssertionError("Compact Explorer summary/action missing")
    bounds = []
    for node in (names[0], actions[0]):
        match = re.fullmatch(
            r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
            node.attrib.get("bounds", ""))
        if not match:
            raise AssertionError("Explorer summary bounds missing")
        bounds.append(tuple(map(int, match.groups())))
    title, action = bounds
    if action[1] < title[3]:
        raise AssertionError(
            f"Explorer edit-plan chip obscures truncated APK name: "
            f"title={title} action={action}")


def check_screen(name, required_text, width_px, height_px, api, density):
    smoke.tap(smoke.find_tab(smoke.visible_app_hierarchy(), name))
    smoke.ensure_foreground()
    nodes = smoke.visible_app_hierarchy()
    assert "selecionada" in smoke.find_tab(nodes, name).attrib.get(
        "content-desc", ""), f"{name}: tab not selected"
    assert any(n.attrib.get("text") == required_text for n in nodes), (
        f"{name}: essential visible heading missing at 320 dp / 130% font")
    # Bottom navigation must remain reachable and onscreen after font scaling.
    for tab_name in ("Início", "Arquivos", "Segurança", "Build", "Design"):
        node = smoke.find_tab(nodes, tab_name)
        bounds = node.attrib.get("bounds", "")
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
        assert match, f"{tab_name}: missing bounds in compact layout"
        x1, y1, x2, y2 = map(int, match.groups())
        assert 0 <= x1 < x2 <= width_px and 0 <= y1 < y2 <= height_px, (
            f"{tab_name}: bottom tab clipped outside compact display: {bounds}")
        assert x2 - x1 >= round(48 * width_px / 320), (
            f"{tab_name}: bottom tab has less than 48 dp width")
    if name == "Início":
        for description in ("Abrir menu de navegação",
                            "Abrir personalização"):
            require_accessible_target(
                nodes, description, density, (width_px, height_px))
        print(f"P7_COMPACT_HOME_A11Y_PASS api={api} 48dp targets=2",
              flush=True)
    if name == "Arquivos":
        require_stacked_explorer_summary(nodes)
        for description in ("Ir à raiz do APK",
                            "Abrir plano de edição"):
            require_accessible_target(
                nodes, description, density, (width_px, height_px))
        print(f"P7_COMPACT_EXPLORER_A11Y_PASS api={api} 48dp targets=2",
              flush=True)
    if name == "Design":
        # All four real Design subtabs must fit simultaneously in the 320dp
        # viewport at 130% system text. No offscreen-only "Logotipo" action.
        # Each tab still needs a full 48dp target, and no APK is touched.
        for description in ("Temas, aba selecionada",
                            "Layout, selecionar aba",
                            "Ícones, selecionar aba",
                            "Logotipo, selecionar aba",
                            "Ver todos: Previews de Temas"):
            require_accessible_target(
                nodes, description, density, (width_px, height_px))
        print(f"P7_COMPACT_DESIGN_A11Y_PASS api={api} 48dp targets=5",
              flush=True)
    filename = f"p7-compact-{name.lower().replace('í', 'i')}-android-{api}.png"
    with open(filename, "wb") as screenshot:
        screenshot.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    print(f"P7_COMPACT_SCREEN_PASS api={api} section={name} "
          f"viewport=320dp font=130% screenshot={filename}", flush=True)


def check():
    api = smoke.adb("shell", "getprop", "ro.build.version.sdk").strip()
    if api not in ("29", "35"):
        raise AssertionError(f"Unexpected test emulator API: {api}")
    (original_size, size_override) = parse_wm(
        smoke.adb("shell", "wm", "size"), "size")
    (density_info, _) = parse_wm(
        smoke.adb("shell", "wm", "density"), "density")
    density = density_info[0]
    compact = viewport_pixels(320, 720, density)
    previous_scale = smoke.adb(
        "shell", "settings", "get", "system", "font_scale")
    width_px, height_px = compact
    print(f"P7_COMPACT_START api={api} original={original_size} "
          f"compact={compact} density={density} original_font={previous_scale}",
          flush=True)
    try:
        smoke.adb("shell", "wm", "size", f"{width_px}x{height_px}")
        smoke.adb("shell", "settings", "put", "system", "font_scale", "1.3")
        launch()
        for section, title in (
                ("Início", "Olá, Desenvolvedor"),
                ("Arquivos", "Explorador de Arquivos"),
                ("Design", "Design Studio")):
            check_screen(section, title, width_px, height_px, api, density)
        print(f"P7_COMPACT_PASS api={api} viewport=320dp font=130%",
              flush=True)
    finally:
        # Never leave a test emulator in an altered configuration, even if
        # UI assertions or screenshots fail.
        if size_override is None:
            smoke.adb("shell", "wm", "size", "reset")
        else:
            smoke.adb("shell", "wm", "size",
                      f"{size_override[0]}x{size_override[1]}")
        if previous_scale in ("", "null"):
            smoke.adb("shell", "settings", "delete", "system", "font_scale")
        else:
            smoke.adb("shell", "settings", "put", "system", "font_scale",
                      previous_scale)
        launch()
        print(f"P7_COMPACT_RESTORED api={api}", flush=True)


if __name__ == "__main__":
    check()
