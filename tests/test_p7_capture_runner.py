"""Regression tests for P7 populated-Explorer capture script.

ADB is stubbed; these tests cover orchestration and fail-closed behavior,
not Android visual fidelity or physical-device acceptance.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "p7_capture_populated.sh"


def chunk(tag, data=b""):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))


def png():
    header = struct.pack(">IIBBBBB", 3, 2, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x10\x20\x30\xff" * 3
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(row * 2)) + chunk(b"IEND"))


class P7CaptureRunnerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cwd = Path(temp.name)
        for item in (
            "app/build/outputs/apk/debug/app-debug.apk",
            "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",
        ):
            path = self.cwd / item
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test-only")
        image = self.cwd / "fixture.png"
        image.write_bytes(png())
        bin_dir = self.cwd / "bin"
        bin_dir.mkdir()
        fake_adb = bin_dir / "adb"
        fake_adb.write_text(
            "#!" + sys.executable + "\n"
            "import os,sys,pathlib\n"
            "args=sys.argv[1:]\n"
            "with open(os.environ['P7_ADB_LOG'],'a') as f:\n"
            "  f.write(' '.join(args)+'\\n')\n"
            "if args[0]=='install':\n"
            "  print('Success')\n"
            "elif args[:3]==['shell','am','instrument']:\n"
            "  print(os.environ.get('P7_INSTRUMENT_RESULT','OK (1 test)'))\n"
            "  sys.exit(int(os.environ.get('P7_INSTRUMENT_EXIT','0')))\n"
            "elif args[:4]==['exec-out','run-as','com.readroid.app','cat']:\n"
            "  sys.stdout.buffer.write(pathlib.Path(os.environ['P7_PNG']).read_bytes())\n"
            "elif args[:3]==['shell','getprop','sys.boot_completed']:\n"
            "  print('1')\n"
            "elif args[:3]==['shell','dumpsys','window']:\n"
            "  print('mCurrentFocus=Window{u0 com.android.launcher3/.Launcher}')\n"
            "elif args[:4]==['shell','dumpsys','activity','activities']:\n"
            "  print('topResumedActivity=ActivityRecord{u0 com.android.launcher3/.Launcher}')\n"
            "else:\n"
            "  sys.exit(9)\n",
            encoding="utf-8")
        fake_adb.chmod(0o755)
        self.log = self.cwd / "calls.txt"
        self.env = dict(os.environ)
        self.env.update({
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "PYTHONPATH": str(ROOT),
            "P7_ADB_LOG": str(self.log),
            "P7_PNG": str(image),
        })

    def execute(self, api="29"):
        return subprocess.run(["bash", str(RUNNER), api], cwd=self.cwd,
                              env=self.env, capture_output=True, text=True,
                              timeout=20)

    def test_workflow_keeps_overlay_test_in_suite_and_capture_isolated(self):
        workflow = (ROOT / ".github/workflows/p7-brand-validation.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn(
            "P7ExplorerPopulatedCaptureInstrumentedTest"
            "#detectsSyntheticSystemOverlayBeforeEvidenceExport", workflow)
        self.assertIn("bash tools/p7_capture_populated.sh", workflow)
        # Capture before the long instrumentation run on the freshly started
        # emulator; taking it after the suite races the API35 Pixel Launcher.
        built = workflow.index(
            "gradle --no-daemon :app:assembleDebug :app:assembleDebugAndroidTest")
        captured = workflow.index("bash tools/p7_capture_populated.sh")
        regression = workflow.index(
            "gradle --no-daemon :app:connectedDebugAndroidTest")
        self.assertLess(built, captured)
        self.assertLess(captured, regression)
        # All three connectedAndroidTest invocations are REQUIRED. The suite
        # may be split for emulator stability but must not shrink or duplicate.
        import re
        commands = re.findall(
            r"gradle --no-daemon :app:connectedDebugAndroidTest "
            r"-Pandroid\.testInstrumentationRunnerArguments\.class=([^\s]+)",
            workflow)
        self.assertEqual(5, len(commands))
        selections = [name for cmd in commands for name in cmd.split(",")]
        self.assertEqual(24, len(selections))
        self.assertEqual(24, len(set(selections)))
        self.assertIn("ram-size: 3072M", workflow)
        self.assertIn("free -m", workflow)
        self.assertEqual(
            ["com.readroid.app.P7BottomNavigationLargeFontInstrumentedTest"],
            commands[0].split(","))
        self.assertEqual(
            ["com.readroid.app.P7WelcomeLargeFontInstrumentedTest"],
            commands[1].split(","))
        self.assertEqual(
            ["com.readroid.app.P7IconTemplatesLargeFontInstrumentedTest"],
            commands[2].split(","))
        self.assertEqual(
            ["com.readroid.app.P7NavigationInstrumentedTest"],
            commands[3].split(","))
        self.assertEqual(20, len(commands[4].split(",")))
        # The runner launches each workflow line as a separate shell.
        # Run the conditional reboot in one guarded executable script.
        marker = "bash tools/p7_api35_reboot.sh ${{ matrix.api }}"
        reboot = workflow.index(marker)
        compact = workflow.index("python3 tools/p7_compact_smoke.py", reboot)
        ordinary = workflow.index(
            "test -s p7-logo-workshop-android-", regression)
        self.assertLess(ordinary, reboot)
        self.assertLess(reboot, compact)
        self.assertEqual(1, workflow.count(marker))
        self.assertIn("bash -n tools/p7_api35_reboot.sh", workflow)
        self.assertEqual(1, workflow.count("python3 tools/p7_compact_smoke.py"))
        self.assertNotIn('if [ "${{ matrix.api }}" = "35" ]; then', workflow)
        guard = (ROOT / "tools/p7_api35_reboot.sh").read_text(
            encoding="utf-8")
        self.assertIn("set -euo pipefail", guard)
        self.assertIn("29)", guard)
        self.assertIn("35)", guard)
        self.assertIn("adb reboot", guard)
        self.assertIn("timeout 150s adb wait-for-device", guard)
        self.assertIn("getprop sys.boot_completed", guard)
        self.assertIn('if [ "$booted" != "1" ]; then', guard)
        self.assertIn("adb shell pm path com.readroid.app", guard)
        self.assertIn("adb shell wm size", guard)
        self.assertIn("adb shell wm density", guard)
        navigation = (ROOT / "app/src/androidTest/java/com/readroid/app/"
                      "P7NavigationInstrumentedTest.java").read_text(
                          encoding="utf-8")
        isolated = (ROOT / "app/src/androidTest/java/com/readroid/app/"
                    "P7BottomNavigationLargeFontInstrumentedTest.java").read_text(
                        encoding="utf-8")
        method = "void bottomNavigationScalesWithoutClippingOrChangingLabels()"
        self.assertNotIn(method, navigation)
        self.assertEqual(1, isolated.count(method))
        self.assertEqual(38, navigation.count("@Test"))
        self.assertEqual(1, isolated.count("@Test"))
        icon_isolated = (ROOT / "app/src/androidTest/java/com/readroid/app/"
                         "P7IconTemplatesLargeFontInstrumentedTest.java").read_text(
                             encoding="utf-8")
        icon_method = "void fourIconTemplatesGrowWithLargeTextAndAnnounceSingleButtons()"
        self.assertNotIn(icon_method, navigation)
        self.assertEqual(1, icon_isolated.count(icon_method))
        self.assertEqual(1, icon_isolated.count("@Test"))
        self.assertIn("Icon label must fit in tile height", icon_isolated)
        self.assertIn("NegrescoTheme.apply(context)", icon_isolated)
        self.assertEqual(1, navigation.count(
            "void themeAndLayoutBadgesRequireCommittedAppearance()"))
        self.assertIn("Pending theme has no applied badge", navigation)
        self.assertIn("Pending layout has no applied badge", navigation)
        studio_state = (ROOT / "app/src/main/java/com/readroid/app/"
            "P7DesignStudio.java").read_text(encoding="utf-8")
        self.assertIn("static String appearanceTileState(", studio_state)
        self.assertIn("P7VisualCatalog.currentLayout(a) == themeSurface",
            studio_state)
        self.assertIn("if (applied) {", studio_state)
        self.assertEqual(1, navigation.count(
            "void repeatedThemeTapNeverStacksOrChangesConfirmedChoice()"))
        self.assertIn("No second theme dialog may replace the first", navigation)
        self.assertIn("Cancel cannot save a theme or any other setting", navigation)
        self.assertIn("activeThemeConfirmation()", (ROOT /
            "app/src/main/java/com/readroid/app/P7DesignStudio.java"
            ).read_text(encoding="utf-8"))
        theme_source = (ROOT /
            "app/src/main/java/com/readroid/app/P7DesignStudio.java"
            ).read_text(encoding="utf-8")
        self.assertIn("if (themeConfirmation != null && themeConfirmation.isShowing()) return;", theme_source)
        self.assertIn("P7ThemeCatalog.apply(a, choice)", theme_source)
        self.assertIn("if (themeConfirmation == dialog) themeConfirmation = null;", theme_source)
        self.assertEqual(1, navigation.count(
            "void repeatedLayoutTapNeverStacksNativeConfirmations()"))
        self.assertIn("Rapid layout taps must preserve one native dialog", navigation)
        self.assertIn("Cancelled repeated layout taps cannot save any setting", navigation)
        studio = (ROOT / "app/src/main/java/com/readroid/app/"
                  "P7DesignStudio.java").read_text(encoding="utf-8")
        self.assertIn("activeLayoutConfirmation()", studio)
        self.assertIn("if (layoutConfirmation != null && layoutConfirmation.isShowing()) return;", studio)
        self.assertIn("if (layoutConfirmation == dialog) layoutConfirmation = null;", studio)
        self.assertEqual(1, navigation.count(
            "void repeatedPresetTapNeverStacksNativeConfirmations()"))
        self.assertIn("No second dialog may replace the first", navigation)
        self.assertIn("Cancelled repeated taps must restore state", navigation)
        self.assertIn("navTabHeightDp(310, 3f, 1.35f, true)", isolated)
        self.assertIn("NegrescoTheme.apply(context)", isolated)
        self.assertIn("Navigation row must reserve enlarged text", isolated)
        welcome = (ROOT / "app/src/androidTest/java/com/readroid/app/"
                   "P7WelcomeLargeFontInstrumentedTest.java").read_text(
                       encoding="utf-8")
        self.assertEqual(1, welcome.count("@Test"))
        self.assertIn("void welcomeCardGrowsWithLongTextInsteadOfClippingIt()", welcome)
        self.assertNotIn("void welcomeCardGrowsWithLongTextInsteadOfClippingIt()",
                         navigation)
        self.assertIn("No hidden ellipsized lines", welcome)
        self.assertIn("description.getLayout().getLineCount() >= 10", welcome)
        self.assertIn("NegrescoTheme.apply(context)", welcome)
        self.assertIn(
            "com.readroid.app.P7ExplorerPopulatedCaptureInstrumentedTest"
            "#detectsSyntheticSystemOverlayBeforeEvidenceExport", selections)
        self.assertIn("com.readroid.app.P7VisualCatalogInstrumentedTest", selections)
        self.assertIn("com.readroid.app.P7ProjectHistoryInstrumentedTest", selections)
        self.assertIn("com.readroid.app.ApkRebuilderInstrumentedTest", selections)
        self.assertEqual(1, workflow.count("bash tools/p7_capture_populated.sh"))
        # Gradle removes the tested target package when instrumented tests
        # finish. The visual capture must reinstall the exact debug target,
        # verify the real installed package and only then launch the Activity.
        restored = workflow.index(
            "adb install -r app/build/outputs/apk/debug/app-debug.apk",
            regression)
        package_check = workflow.index(
            "adb shell pm path com.readroid.app | grep -Fq 'package:'",
            restored)
        launched = workflow.index(
            "adb shell am start -W -n com.readroid.app/.MainActivity",
            package_check)
        self.assertLess(regression, restored)
        self.assertLess(restored, package_check)
        self.assertLess(package_check, launched)
        # The original package check follows instrumentation. API35 has a
        # second mandatory package check after its verified AVD reboot.
        self.assertEqual(1, workflow.count(
            "adb shell pm path com.readroid.app | grep -Fq 'package:'"))
        script = RUNNER.read_text(encoding="utf-8")
        self.assertIn(
            "P7ExplorerPopulatedCaptureInstrumentedTest"
            "#captureRealActivityWithIndexedSyntheticApk", script)
        self.assertIn("OK (1 test)", script)

    def test_valid_real_png_and_shell_state(self):
        result = self.execute()
        self.assertEqual(0, result.returncode, result.stderr)
        source = (ROOT / "app/src/androidTest/java/com/readroid/app/"
                  "P7ExplorerPopulatedCaptureInstrumentedTest.java").read_text(
                      encoding="utf-8")
        self.assertIn("isExactLauncherAnrWindow(String windowDump)", source)
        self.assertIn("com.google.android.apps.nexuslauncher", source)
        self.assertIn("scan.closeCount != 1", source)
        self.assertIn("scan.appAnr", source)
        self.assertIn("if (!scan.launcherAnr && !isExactLauncherAnrFocusedBySystem())",
                      source)
        self.assertIn("isExactLauncherAnrWindow(exact.replace(", source)
        self.assertNotIn("am force-stop", source)
        self.assertNotIn("input keyevent", source)
        self.assertIn("P7_POPULATED_PNG_OK", result.stdout)
        self.assertFalse((self.cwd / "p7-capture-diagnostics-android-29.txt").exists())
        self.assertTrue((self.cwd /
                         "p7-explorer-populated-android-29.png").is_file())
        commands = self.log.read_text()
        self.assertEqual(2, commands.count("install -r "))
        self.assertIn("shell am instrument -w -r", commands)
        self.assertIn("P7ExplorerPopulatedCaptureInstrumentedTest#captureRealActivityWithIndexedSyntheticApk", commands)
        self.assertIn("exec-out run-as com.readroid.app cat", commands)

    def test_invalid_api_rejected_without_adb(self):
        result = self.execute("33")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())

    def test_corrupt_png_fails_closed(self):
        (self.cwd / "fixture.png").write_bytes(b"not PNG")
        result = self.execute()
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("P7_POPULATED_PNG_OK", result.stdout)

    def test_instrumentation_failure_cannot_pass(self):
        self.env["P7_INSTRUMENT_RESULT"] = "FAILURES!!!"
        result = self.execute()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.cwd /
                          "p7-explorer-populated-android-29.png").exists())
        diag = self.cwd / "p7-capture-diagnostics-android-29.txt"
        self.assertTrue(diag.is_file(), result.stderr)
        content = diag.read_text(encoding="utf-8")
        self.assertIn("P7_CAPTURE_DIAGNOSTICS api=29", content)
        self.assertIn("instrument_exit=0", content)
        self.assertIn("mCurrentFocus=Window{u0 com.android.launcher3/.Launcher}", content)
        self.assertIn("topResumedActivity=ActivityRecord", content)
        commands = self.log.read_text()
        self.assertIn("shell dumpsys window", commands)
        self.assertIn("shell dumpsys activity activities", commands)

    def test_instrumentation_adb_nonzero_blocks_and_leaves_diagnostics(self):
        self.env["P7_INSTRUMENT_EXIT"] = "16"
        result = self.execute("35")
        self.assertNotEqual(0, result.returncode)
        diag = self.cwd / "p7-capture-diagnostics-android-35.txt"
        self.assertTrue(diag.is_file())
        self.assertIn("instrument_exit=16", diag.read_text())
        self.assertFalse((self.cwd /
                          "p7-explorer-populated-android-35.png").exists())

    def test_missing_android_test_package_cannot_pass(self):
        (self.cwd /
         "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk").unlink()
        result = self.execute()
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
