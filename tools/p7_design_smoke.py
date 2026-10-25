#!/usr/bin/env python3
"""Smoke and screenshot of the real Design Studio on Android 10/15.

No user APK or saved project is required for this visual regression capture.
"""
import subprocess
import time
import re
try:
    from tools import android_ui_smoke as smoke
except ImportError:
    import android_ui_smoke as smoke


def saved_identity_preview(nodes):
    """Require exactly one real, informative and non-interactive saved-brand preview."""
    prefix = "Prévia da identidade visual atual. Nome: "
    matching = [node for node in nodes
                if node.attrib.get("content-desc", "").startswith(prefix)]
    assert len(matching) == 1, "Saved identity preview must be unique"
    description = matching[0].attrib["content-desc"]
    name, separator, subtitle = description[len(prefix):].partition(". Subtítulo: ")
    assert separator and name.strip() and subtitle.strip(), (
        "Saved identity must announce both nonempty name and subtitle")
    assert matching[0].attrib.get("clickable") != "true", (
        "Saved identity preview is informative, never an action")
    return description


def applied_theme_preview(nodes):
    """Require exactly one clickable, committed catalog theme, never a pending preview."""
    approved = ("Negreco Blue", "Carbon Dark", "Matrix Green", "Sunset")
    matching = [n for n in nodes
                if ", tema aplicado" in n.attrib.get("content-desc", "")
                and n.attrib.get("content-desc", "").startswith(approved)]
    assert len(matching) == 1, "A saved theme must be reflected in its preview"
    assert matching[0].attrib.get("clickable") == "true", (
        "Saved theme must still expose a real clickable catalog card")
    description = matching[0].attrib["content-desc"]
    name, state = description.split(", tema aplicado", 1)
    assert name in approved and state.startswith(". "), (
        "Applied theme must announce its actual glow state and subtitle")
    assert state[2:].startswith(("Neon · ", "Sem brilho · ")), (
        "Applied theme must distinguish glow state for TalkBack")
    return description



def require_four_theme_previews(nodes, screen_width_px, density):
    """At the 393dp baseline, four actual selectable themes must fit onscreen.

    This verifies the Android accessibility bounds, not an illustrative bitmap.
    Bigger text and other viewport families retain their scrollable catalog.
    """
    names = ("Negreco Blue", "Carbon Dark", "Matrix Green", "Sunset")
    cards = []
    for name in names:
        matches = [node for node in nodes
                   if node.attrib.get("content-desc", "").startswith(
                       name + ", ")
                   and node.attrib.get("clickable") == "true"]
        if len(matches) != 1:
            raise AssertionError(
                f"Expected exactly one native theme card {name!r}, "
                f"found {len(matches)}")
        match = re.fullmatch(
            r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
            matches[0].attrib.get("bounds", ""))
        if not match:
            raise AssertionError(f"No real bounds for theme {name}")
        x1, y1, x2, y2 = map(int, match.groups())
        if not (0 <= x1 < x2 <= screen_width_px and y1 < y2):
            raise AssertionError(f"Theme {name} is clipped: {match.group()}")
        if (x2 - x1) * 160 < density * 70:
            raise AssertionError(
                f"Theme {name} is too narrow or clipped to read")
        cards.append((x1, y1, x2, y2))
    for before, after in zip(cards, cards[1:]):
        if before[2] > after[0] + 2:
            raise AssertionError("Reference theme previews overlap")
        if after[1] >= before[3] or before[1] >= after[3]:
            raise AssertionError("Reference theme previews do not share a row")
    return cards



def require_five_preset_previews(nodes, screen_width_px, density):
    """At the reference phone width, all five native preset cards share a rail.

    No screenshot trick: inspect accessible, operable nodes and their bounds.
    Each tile retains at least a 48dp target. Enlarged text remains scrollable.
    """
    names = ("Dark OLED", "Cyber Neon", "Minimal", "Glass", "Retro")
    boxes = []
    for name in names:
        matches = [node for node in nodes
                   if node.attrib.get("content-desc", "").startswith(name + ", ")
                   and node.attrib.get("clickable") == "true"]
        if len(matches) != 1:
            raise AssertionError(f"Missing/duplicated real preset {name}: "
                                 f"{len(matches)}")
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                             matches[0].attrib.get("bounds", ""))
        if match is None:
            raise AssertionError(f"Preset {name} lacks Android bounds")
        x1, y1, x2, y2 = map(int, match.groups())
        if not (0 <= x1 < x2 <= screen_width_px and y1 < y2):
            raise AssertionError(f"Preset {name} clipped: {match.group()}")
        if (x2 - x1) * 160 < density * 48:
            raise AssertionError(f"Preset {name} lost 48dp touch target")
        boxes.append((x1, y1, x2, y2))
    for left, right in zip(boxes, boxes[1:]):
        if left[2] > right[0] + 2:
            raise AssertionError("Native preset cards overlap")
        if left[1] >= right[3] or right[1] >= left[3]:
            raise AssertionError("Presets no longer share one reference row")
    return boxes


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
    # The approved 393dp Home/Design board shows four compact previews,
    # not three tiles and a barely visible sliver of the fourth.
    size = smoke.adb("shell", "wm", "size")
    density_info = smoke.adb("shell", "wm", "density")
    try:
        from tools.p7_compact_smoke import parse_wm
    except ImportError:
        from p7_compact_smoke import parse_wm
    (width_px, _), _ = parse_wm(size, "size")
    (density,), _ = parse_wm(density_info, "density")
    width_dp = width_px * 160 / density
    if 390 <= width_dp < 420:
        require_four_theme_previews(nodes, width_px, density)
        require_five_preset_previews(nodes, width_px, density)
        print(f"P7_FOUR_THEMES_PASS api={smoke.adb('shell', 'getprop', 'ro.build.version.sdk').strip()}",
              flush=True)
        print(f"P7_FIVE_PRESETS_PASS api={smoke.adb('shell', 'getprop', 'ro.build.version.sdk').strip()}",
              flush=True)
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
    saved_theme = applied_theme_preview(before)
    theme = "Matrix Green" if not saved_theme.startswith("Matrix Green") else "Negreco Blue"
    # The accessible label now includes the actual glow state and subtitle:
    # "Matrix Green, selecionar prévia. Neon · Hacker Style".
    # Match the exact card-name/state prefix, then REQUIRE that the spoken
    # theme variant is present. Do not loosen the check to name-only.
    spoken_prefix = theme + ", selecionar prévia. "
    matches = [n for n in before
               if n.attrib.get("content-desc", "").startswith(spoken_prefix)
               and n.attrib.get("clickable") == "true"
               and n.attrib.get("content-desc", "")[len(spoken_prefix):]
                   .startswith(("Neon · ", "Sem brilho · "))]
    assert len(matches) == 1, (
        "Unselected theme must be uniquely clickable and describe its glow")
    tile = matches[0]
    smoke.tap(tile)
    modal = {n.attrib.get("text", "") for n in smoke.visible_app_hierarchy()}
    assert "Aplicar " + theme + "?" in modal, (
        "Theme preview did not open a real confirmation")
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    after = smoke.visible_app_hierarchy()
    assert any(n.attrib.get("content-desc") == saved_theme for n in after), (
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
    templates = [n for n in icon_nodes if n.attrib.get("content-desc") ==
                 "Personalizar ícone Código Neon"]
    assert len(templates) == 1, "Original icon template gallery missing"
    smoke.tap(templates[0])
    workshop = smoke.visible_app_hierarchy()
    workshop_texts = {n.attrib.get("text", "") for n in workshop}
    for expected in ("Criador de Ícones", "Cor", "Símbolo",
                     "Formato", "Exportar PNG"):
        assert expected in workshop_texts, (
            "Native icon workshop missing real control " + expected)
    export_actions = [n for n in workshop
                      if n.attrib.get("text") == "Exportar PNG"
                      and n.attrib.get("content-desc") == "Exportar PNG 512×512"
                      and n.attrib.get("clickable") == "true"]
    assert len(export_actions) == 1, (
        "Export button must be uniquely visible and clickable inside the editor")
    with open(f"p7-icon-workshop-android-{api}.png", "wb") as stream:
        stream.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    assert any(n.attrib.get("content-desc") == "Prévia original do ícone"
               for n in workshop), "Native Canvas icon preview not displayed"
    # This template must preselect its real saved-to-PNG drawing parameters.
    for choice in ("Violeta", "Código", "Circular"):
        assert any(n.attrib.get("text") == choice
                   and n.attrib.get("checked") == "true"
                   for n in workshop), (
            "Catalog template did not initialize option " + choice)
    # Cancel, don't create an APK or write a PNG during CI smoke.
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    logo_nodes = smoke.visible_app_hierarchy()
    logo_tabs = [n for n in logo_nodes if n.attrib.get("text") == "Logotipo"
                 and n.attrib.get("clickable") == "true"]
    assert len(logo_tabs) == 1, "Logo Studio tab missing"
    smoke.tap(logo_tabs[0])
    logo_page = smoke.visible_app_hierarchy()
    spoken_identity = saved_identity_preview(logo_page)
    logo_create = [n for n in logo_page if n.attrib.get("text", "").startswith(
                   "Criar logo PNG  ↗") and n.attrib.get("clickable") == "true"]
    assert len(logo_create) == 1, "Real logo editor entry missing"
    smoke.tap(logo_create[0])
    editor_nodes = smoke.visible_app_hierarchy()
    editor_text = {n.attrib.get("text", "") for n in editor_nodes}
    assert "Criador de Logos" in editor_text, "Native logo editor did not open"
    assert "Exportar logo PNG" in editor_text, "Logo export action missing"
    assert any(n.attrib.get("content-desc") == "Prévia original do logo"
               for n in editor_nodes), "Logo preview missing"
    assert any(n.attrib.get("content-desc") == "Exportar logo PNG 1024×512"
               and n.attrib.get("clickable") == "true" for n in editor_nodes), (
        "Logo exporter must be a functional accessible action")
    with open(f"p7-logo-workshop-android-{api}.png", "wb") as stream:
        stream.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    smoke.adb("shell", "input", "keyevent", "4")
    smoke.ensure_foreground()
    assert saved_identity_preview(smoke.visible_app_hierarchy()) == spoken_identity, (
        "Canceling logo edit must return to the unchanged saved identity")
    print(f"P7_DESIGN_PASS api={api} screenshot={target} "
          "apply_cancel=ok icon_workshop=ok saved_logo=ok", flush=True)


if __name__ == "__main__":
    check()
