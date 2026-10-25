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
        self.assertEqual(8, len(commands))
        selections = [name for cmd in commands for name in cmd.split(",")]
        self.assertEqual(27, len(selections))
        self.assertEqual(27, len(set(selections)))
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
            ["com.readroid.app.P7DesignCatalogLargeFontInstrumentedTest"],
            commands[3].split(","))
        self.assertEqual(
            ["com.readroid.app.P7LogoIdentityLargeFontInstrumentedTest"],
            commands[4].split(","))
        self.assertEqual(
            ["com.readroid.app.P7CreatorCardsLargeFontInstrumentedTest"],
            commands[5].split(","))
        self.assertEqual(
            ["com.readroid.app.P7NavigationInstrumentedTest"],
            commands[6].split(","))
        self.assertEqual(20, len(commands[7].split(",")))
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
        self.assertEqual(43, navigation.count("@Test"))
        creator_isolated = (ROOT / "app/src/androidTest/java/com/readroid/app/"
            "P7CreatorCardsLargeFontInstrumentedTest.java").read_text(
                encoding="utf-8")
        creator_method = "void enlargedFontsStackCreatorCardsWithoutLosingActions()"
        self.assertEqual(1, creator_isolated.count("@Test"))
        self.assertEqual(1, creator_isolated.count(creator_method))
        self.assertNotIn(creator_method, navigation)
        self.assertIn("shouldStackCreators(393, 1.25f, 1f)", creator_isolated)
        self.assertIn("shouldStackCreators(393, 1f, 1.35f)", creator_isolated)
        self.assertIn('putInt("font_percent", 135)', creator_isolated)
        self.assertIn("LinearLayout.VERTICAL", creator_isolated)
        self.assertIn("Button.class.getName()", creator_isolated)
        self.assertIn("NegrescoTheme.apply(context)", creator_isolated)
        logo_isolated = (ROOT / "app/src/androidTest/java/com/readroid/app/"
            "P7LogoIdentityLargeFontInstrumentedTest.java").read_text(
                encoding="utf-8")
        self.assertEqual(1, logo_isolated.count("@Test"))
        self.assertEqual(1, logo_isolated.count(
            "void logoPreviewAnnouncesSavedNameAndSubtitleWithoutDuplicateNodes()"))
        self.assertNotIn(
            "void logoPreviewAnnouncesSavedNameAndSubtitleWithoutDuplicateNodes()",
            navigation)
        self.assertIn("display_name", logo_isolated)
        self.assertIn("display_subtitle", logo_isolated)
        self.assertIn("font_percent", logo_isolated)
        self.assertIn("NO_HIDE_DESCENDANTS", logo_isolated)
        self.assertIn("assertEquals(Integer.MAX_VALUE", logo_isolated)
        self.assertIn("NegrescoTheme.apply(context)", logo_isolated)
        isolated_design = (ROOT / "app/src/androidTest/java/com/readroid/app/"
            "P7DesignCatalogLargeFontInstrumentedTest.java").read_text(
                encoding="utf-8")
        self.assertEqual(1, isolated_design.count("@Test"))
        self.assertIn("void enlargedTextRetainsCompleteThemeAndPresetLabels()",
                      isolated_design)
        self.assertNotIn("void enlargedTextRetainsCompleteThemeAndPresetLabels()",
                         navigation)
        self.assertIn("for (int i = 0; i < P7ThemeCatalog.count(); i++)",
                      isolated_design)
        self.assertIn("for (String name : P7VisualCatalog.PRESET_NAMES)",
                      isolated_design)
        self.assertIn("assertAccessibleButton(tile)", isolated_design)
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
            "void viewAllWaitsForThemeConfirmationAndRecoversAfterCancel()"))
        self.assertIn("View All may not appear behind Apply confirmation", navigation)
        self.assertEqual(1, navigation.count(
            "void viewAllWaitsForLayoutConfirmationAndRecoversAfterCancel()"))
        self.assertEqual(1, navigation.count(
            "void viewAllWaitsForPresetConfirmationAndRecoversAfterCancel()"))
        self.assertIn("assertViewAllBlockedByNonThemeConfirmation(1)", navigation)
        self.assertIn("assertViewAllBlockedByNonThemeConfirmation(2)", navigation)
        self.assertIn("View All cannot stack behind Layout/Preset Apply", navigation)
        self.assertIn("View All cannot replace the current confirmation", navigation)
        self.assertIn("Catalog never persisted unconfirmed options", navigation)
        self.assertIn("Fechar must release the native chooser", navigation)
        self.assertEqual(1, navigation.count(
            "void androidBackClosesEveryCatalogWithoutCommittingAppearance()"))
        self.assertIn("Android Back must dismiss native chooser", navigation)
        self.assertIn("Android Back must clear native chooser handle", navigation)
        self.assertIn("Android Back cannot commit catalog values", navigation)
        self.assertIn("Catalog must reopen after Back", navigation)
        self.assertIn("Reopening and closing must never save appearance", navigation)


        self.assertIn("View All must work normally after Cancel", navigation)
        self.assertEqual(1, navigation.count(
            "void crossFamilyAppearanceConfirmationsNeverStackOrLeavePhantomPreview()"))
        self.assertIn("Layout cannot stack behind theme confirmation", navigation)
        self.assertIn("Theme cannot stack behind layout confirmation", navigation)
        self.assertIn("Theme must finish dismissal before next modal", navigation)
        self.assertIn("Layout OnDismiss must release its reference", navigation)
        self.assertIn("Theme must close before layout can open", navigation)
        self.assertIn("Both cancels preserve all appearance preferences", navigation)
        self.assertGreaterEqual(navigation.count(
            "InstrumentationRegistry.getInstrumentation().waitForIdleSync()"), 5)

        self.assertIn("Layout cannot stack behind preset confirmation", navigation)
        all_dialogs = (ROOT / "app/src/main/java/com/readroid/app/"
            "P7DesignStudio.java").read_text(encoding="utf-8")
        self.assertIn("private boolean appearanceDialogShowing()", all_dialogs)
        self.assertIn("if (appearanceDialogShowing()) {", all_dialogs)
        self.assertEqual(3, all_dialogs.count("if (appearanceDialogShowing()) {"))
        for guard in ("themeConfirmation", "layoutConfirmation",
                      "presetConfirmation", "catalogChooser"):
            self.assertIn(guard + " != null && " + guard + ".isShowing()", all_dialogs)
        self.assertIn("selectedLayout = P7VisualCatalog.currentLayout(a);", all_dialogs)
        self.assertIn("selectedPreset = P7VisualCatalog.currentPreset(a);", all_dialogs)
        self.assertEqual(1, navigation.count(
            "void catalogSelectionsRequireNativeConfirmationBeforeSaving()"))
        self.assertIn("Confirmation must match selected catalog option", navigation)
        self.assertIn("Selecting option cannot persist without Apply", navigation)
        self.assertIn("Cancel preserves complete appearance state", navigation)
        self.assertEqual(1, navigation.count(
            "void repeatedViewAllNeverStacksNativeCatalogChoosers()"))
        self.assertIn("View All cannot stack a second native chooser", navigation)
        self.assertIn("Closing a chooser cannot save appearance", navigation)
        catalog_source = (ROOT / "app/src/main/java/com/readroid/app/"
            "P7DesignStudio.java").read_text(encoding="utf-8")
        self.assertIn("activeCatalogChooser()", catalog_source)
        self.assertIn("if (catalogChooser != null && catalogChooser.isShowing()) return;", catalog_source)
        self.assertIn("if (catalogChooser == chooser) catalogChooser = null;", catalog_source)
        self.assertEqual(1, navigation.count(
            "void customThemeOpensDesignWithoutFakeAppliedBadge()"))
        self.assertIn("Custom theme cannot have an applied check", navigation)
        self.assertIn("Noncatalog accent has no selected catalog theme", navigation)
        self.assertIn("committedTheme >= 0", (ROOT /
            "app/src/main/java/com/readroid/app/P7DesignStudio.java"
            ).read_text(encoding="utf-8"))
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
        theme_apply = theme_source.split("private void applySelectedTheme()", 1)[1]
        theme_apply = theme_apply.split("private int selectedLayout", 1)[0]
        self.assertIn("if (appearanceDialogShowing()) {", theme_apply)
        self.assertIn("restoreCurrentTheme();", theme_apply)
        self.assertIn("render();", theme_apply)
        self.assertIn("P7ThemeCatalog.apply(a, choice)", theme_source)
        self.assertIn("if (themeConfirmation == dialog) themeConfirmation = null;", theme_source)
        preset_apply = theme_source.split("private void confirmPreset()", 1)[1]
        preset_apply = preset_apply.split("private void showError(", 1)[0]
        self.assertIn("if (appearanceDialogShowing()) {", preset_apply)
        self.assertIn("selectedPreset = P7VisualCatalog.currentPreset(a);",
            preset_apply)
        self.assertIn("render();", preset_apply)
        self.assertEqual(1, navigation.count(
            "void repeatedLayoutTapNeverStacksNativeConfirmations()"))
        self.assertIn("Rapid layout taps must preserve one native dialog", navigation)
        self.assertIn("Cancelled repeated layout taps cannot save any setting", navigation)
        studio = (ROOT / "app/src/main/java/com/readroid/app/"
                  "P7DesignStudio.java").read_text(encoding="utf-8")
        self.assertIn("activeLayoutConfirmation()", studio)
        layout_apply = studio.split("private void confirmLayout()", 1)[1]
        layout_apply = layout_apply.split("private void confirmPreset()", 1)[0]
        self.assertIn("if (appearanceDialogShowing()) {", layout_apply)
        self.assertIn("selectedLayout = P7VisualCatalog.currentLayout(a);",
            layout_apply)
        self.assertIn("render();", layout_apply)
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
        self.assertIn("private static String boundedForegroundEvidence(String dump)",
                      source)
        self.assertIn("private static String readForegroundEvidenceOnce()", source)
        self.assertIn("focusedSystemWindows=", source)
        self.assertIn("no unrelated overlay was dismissed", source)
        self.assertIn("focused.contains(\"mCurrentFocus=Window{\")", source)
        self.assertIn("focused.contains(\"mFocusedApp=ActivityRecord{\")", source)
        self.assertIn("boundedForegroundEvidence(oversized).length() <= 240", source)
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
