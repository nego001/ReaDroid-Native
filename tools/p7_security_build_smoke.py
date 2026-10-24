#!/usr/bin/env python3
"""P7 real Security/Build screenshots and safe operational smoke on API 29/35.

No import, APK export, signing, keystore creation or plan deletion.
"""
import subprocess

try:
    from tools import android_ui_smoke as ui
except ImportError:
    import android_ui_smoke as ui


def require_text(nodes, text):
    found = [n for n in nodes if n.attrib.get("text") == text]
    if not found:
        raise AssertionError(f"Missing visible text: {text!r}")
    return found[0]


def require_clickable(nodes, prefix):
    found = [n for n in nodes
             if n.attrib.get("content-desc", "").startswith(prefix)
             and n.attrib.get("clickable") == "true"
             and n.attrib.get("enabled") == "true"]
    if len(found) != 1:
        raise AssertionError(f"Expected one enabled action {prefix}, got {len(found)}")
    return found[0]


def capture_section(api, tab, heading, action, slug):
    ui.tap(ui.find_tab(ui.visible_app_hierarchy(), tab))
    ui.ensure_foreground()
    nodes = ui.visible_app_hierarchy()
    selected = ui.find_tab(nodes, tab).attrib.get("content-desc", "")
    if "selecionada" not in selected:
        raise AssertionError(f"Navigation failed to select {tab}")
    require_text(nodes, heading)
    control = require_clickable(nodes, action)
    screenshot = f"p7-{slug}-android-{api}.png"
    with open(screenshot, "wb") as output:
        output.write(subprocess.check_output(
            ["adb", "exec-out", "screencap", "-p"], timeout=45))
    print(f"P7_FEATURE_SCREEN_PASS api={api} section={tab} screenshot={screenshot}",
          flush=True)
    return control


def check():
    api = ui.adb("shell", "getprop", "ro.build.version.sdk").strip()
    if api not in ("29", "35"):
        raise AssertionError("Unexpected Android API")
    ui.ensure_foreground()

    guide = capture_section(api, "Segurança", "Segurança",
                            "Assinatura: requisitos e segurança.", "security")
    # A documented limitation, not a private-key or signing operation.
    ui.tap(guide)
    dialog = ui.visible_app_hierarchy()
    require_text(dialog, "Assinatura de APK modificado")
    # On Android 10 the dialog's action button may not be represented
    # as a visible TextView in uiautomator XML. The real title plus the
    # explicit Android Back round-trip verifies safe, operable navigation.
    ui.adb("shell", "input", "keyevent", "4")
    ui.ensure_foreground()
    if "selecionada" not in ui.find_tab(
            ui.visible_app_hierarchy(), "Segurança").attrib.get("content-desc", ""):
        raise AssertionError("Security guide did not return to Security")

    review = capture_section(api, "Build", "Construir",
                             "Revisar alterações pendentes.", "build")
    # Read-only plan dialog. Never invoke clear/export/rebuild.
    ui.tap(review)
    dialog = ui.visible_app_hierarchy()
    headings = {n.attrib.get("text", "") for n in dialog}
    if "Plano de alterações" not in headings and not any(
            x.startswith("Alterações pendentes (") for x in headings):
        raise AssertionError("Real build review dialog is missing")
    ui.adb("shell", "input", "keyevent", "4")
    ui.ensure_foreground()
    if "selecionada" not in ui.find_tab(
            ui.visible_app_hierarchy(), "Build").attrib.get("content-desc", ""):
        raise AssertionError("Build review did not return to Build")
    print(f"P7_SECURITY_BUILD_PASS api={api} guide=ok plan_review=ok screenshots=2",
          flush=True)


if __name__ == "__main__":
    check()
