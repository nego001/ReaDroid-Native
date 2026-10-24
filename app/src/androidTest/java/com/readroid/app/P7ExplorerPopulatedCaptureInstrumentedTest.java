package com.readroid.app;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Canvas;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.View;
import android.view.ViewGroup;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.io.FileOutputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import android.os.ParcelFileDescriptor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Capture a populated, real Explorer UI with a synthetic QA ZIP only. */
@RunWith(AndroidJUnit4.class)
public final class P7ExplorerPopulatedCaptureInstrumentedTest {
    private static final String SCREENSHOT = "p7-explorer-populated.png";
    private static final String[] ENTRIES = {
        "AndroidManifest.xml", "classes.dex", "assets/readme.txt",
        "assets/config.json", "res/drawable/demo.png",
        "res/xml/preferences.xml", "lib/arm64-v8a/libsample.so"
    };

    private static void writeFixture(File target) throws Exception {
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(target))) {
            for (String path : ENTRIES) {
                zip.putNextEntry(new ZipEntry(path));
                zip.write(("P7 synthetic QA only: " + path)
                    .getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        }
    }

    private static void setField(MainActivity activity, String name, Object value)
            throws Exception {
        Field field = MainActivity.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(activity, value);
    }

    private static View byDescription(View node, String label) {
        CharSequence desc = node.getContentDescription();
        if (desc != null && label.equals(desc.toString())) return node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = byDescription(group.getChildAt(i), label);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static View filesTab(View node) {
        CharSequence desc = node.getContentDescription();
        if (desc != null && desc.toString().startsWith("Seção Arquivos")
                && node.isClickable()) return node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = filesTab(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }

    private static JSONObject report(File apk) throws Exception {
        JSONArray files = new JSONArray();
        for (String path : ENTRIES) {
            String detail = "P7 synthetic QA only: " + path;
            String category = path.startsWith("assets/") ? "Assets"
                : path.endsWith(".so") ? "Bibliotecas" : "Recursos";
            files.put(new JSONObject().put("path", path)
                .put("sizeBytes", detail.getBytes(StandardCharsets.UTF_8).length)
                .put("category", category));
        }
        return new JSONObject().put("entries", ENTRIES.length)
            .put("sizeBytes", apk.length()).put("assets", 2)
            .put("manifestAnalysis", new JSONObject()
                .put("packageName", "APK sintético de QA"))
            .put("explorer", new JSONObject().put("files", files));
    }


    /**
     * An isolated screenshot is invalid if any system modal covers the app.
     * Android 15 may show the Pixel Launcher ANR independently of our app.
     * Only that exact dialog, with the exact Android close action, can be
     * dismissed once. An app ANR, unrelated modal or missing UI data FAILS.
     */
    private static boolean isLauncherAnrNode(AccessibilityNodeInfo node) {
        return "android".contentEquals(
                node.getPackageName() == null ? "" : node.getPackageName())
            && "Pixel Launcher isn't responding".contentEquals(
                node.getText() == null ? "" : node.getText());
    }

    private static boolean isAppAnrNode(AccessibilityNodeInfo node) {
        CharSequence text = node.getText();
        return text != null && (
            "NegrecoDroid isn't responding".contentEquals(text)
            || "NegrescoDroid isn't responding".contentEquals(text));
    }

    private static boolean isLauncherCloseNode(AccessibilityNodeInfo node) {
        return "android".contentEquals(
                node.getPackageName() == null ? "" : node.getPackageName())
            && "android:id/aerr_close".equals(node.getViewIdResourceName())
            && node.isClickable();
    }

    private static final class OverlayScan {
        boolean launcherAnr;
        boolean appAnr;
        int closeCount;
        AccessibilityNodeInfo closeNode;
    }

    private static void collectOverlay(AccessibilityNodeInfo node,
            OverlayScan scan) {
        if (isLauncherAnrNode(node)) scan.launcherAnr = true;
        if (isAppAnrNode(node)) scan.appAnr = true;
        if (isLauncherCloseNode(node)) {
            scan.closeCount++;
            if (scan.closeNode == null)
                scan.closeNode = AccessibilityNodeInfo.obtain(node);
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child == null) continue;
            try {
                collectOverlay(child, scan);
            } finally {
                child.recycle();
            }
        }
    }

    /**
     * Android 15 may identify the known Pixel Launcher ANR by its process name
     * while accessibility text is localized. Confirm BOTH focused window and
     * focused Activity before allowing the existing Android close button.
     * This alone NEVER dismisses a modal or approves any screenshot.
     */
    private static boolean isExactLauncherAnrWindow(String windowDump) {
        boolean exactAnrWindow = false;
        boolean exactFocusedApp = false;
        for (String row : windowDump.split("\n")) {
            String line = row.trim();
            if (line.startsWith("mCurrentFocus=Window{")
                    && line.contains("Application Not Responding: "
                        + "com.google.android.apps.nexuslauncher}"))
                exactAnrWindow = true;
            if (line.startsWith("mFocusedApp=ActivityRecord{")
                    && line.contains("com.google.android.apps.nexuslauncher/"
                        + ".NexusLauncherActivity"))
                exactFocusedApp = true;
        }
        return exactAnrWindow && exactFocusedApp;
    }

    private static boolean isExactLauncherAnrFocusedBySystem() {
        ParcelFileDescriptor pipe = null;
        try {
            pipe = InstrumentationRegistry.getInstrumentation().getUiAutomation()
                .executeShellCommand("dumpsys window | grep -E "
                    + "'mCurrentFocus=|mFocusedApp='");
            if (pipe == null) return false;
            try (BufferedReader stream = new BufferedReader(
                    new InputStreamReader(
                        new ParcelFileDescriptor.AutoCloseInputStream(pipe),
                        StandardCharsets.UTF_8))) {
                pipe = null; // the reader now owns/terminates the descriptor
                StringBuilder output = new StringBuilder(1024);
                String line;
                while ((line = stream.readLine()) != null) {
                    if (output.length() + line.length() > 4096) return false;
                    output.append(line).append('\n');
                }
                return isExactLauncherAnrWindow(output.toString());
            }
        } catch (Exception unavailable) {
            // Failure to inspect the OS means no recovery, never an approval.
            return false;
        } finally {
            if (pipe != null) {
                try { pipe.close(); } catch (java.io.IOException ignored) { }
            }
        }
    }

    private static boolean dismissKnownLauncherAnrOnce() {
        AccessibilityNodeInfo active = InstrumentationRegistry
            .getInstrumentation().getUiAutomation().getRootInActiveWindow();
        if (active == null) return false;
        OverlayScan scan = new OverlayScan();
        try {
            collectOverlay(active, scan);
            // Never dismiss our own ANR. Require one unambiguous system
            // close action before touching anything outside the app.
            if (scan.appAnr || scan.closeCount != 1
                    || scan.closeNode == null) return false;
            // First use the existing precise accessibility label. Only if it
            // is absent, demand the Android window AND Activity both identify
            // the exact Pixel Launcher ANR before clicking the one OS control.
            if (!scan.launcherAnr && !isExactLauncherAnrFocusedBySystem())
                return false;
            return scan.closeNode.performAction(
                AccessibilityNodeInfo.ACTION_CLICK);
        } finally {
            if (scan.closeNode != null) scan.closeNode.recycle();
            active.recycle();
        }
    }

    private static boolean waitForExplorerFocus(
            ActivityScenario<MainActivity> scenario, long timeoutMillis) {
        boolean[] hasFocus = {false};
        long deadline = android.os.SystemClock.uptimeMillis() + timeoutMillis;
        do {
            scenario.onActivity(activity -> {
                View decor = activity.getWindow().getDecorView();
                hasFocus[0] = decor.hasWindowFocus()
                    && !activity.isFinishing() && !activity.isDestroyed();
            });
            if (hasFocus[0]) return true;
            android.os.SystemClock.sleep(200L);
        } while (android.os.SystemClock.uptimeMillis() < deadline);
        return false;
    }

    private static void assertExplorerWindowInForeground(
            ActivityScenario<MainActivity> scenario) {
        boolean hasFocus = waitForExplorerFocus(scenario, 8000L);
        if (!hasFocus && dismissKnownLauncherAnrOnce()) {
            // This recovers ONLY a confirmed Pixel Launcher ANR. Recheck the
            // real Activity; do not infer success from clicking the OS dialog.
            hasFocus = waitForExplorerFocus(scenario, 6000L);
        }
        assertTrue("Explorer Activity lost foreground window focus after "
            + "bounded recovery; no unrelated overlay was dismissed", hasFocus);
        AccessibilityNodeInfo active = InstrumentationRegistry
            .getInstrumentation().getUiAutomation().getRootInActiveWindow();
        if (active == null) return; // focus + pixel checks remain mandatory
        try {
            CharSequence owner = active.getPackageName();
            assertEquals("An unrelated system window covers the Explorer",
                "com.readroid.app", owner == null ? null : owner.toString());
        } finally {
            active.recycle();
        }
    }

    private static void assertNoBrightSystemOverlay(Bitmap screenshot) {
        assertNotNull(screenshot);
        int paleSamples = 0;
        int totalSamples = 0;
        // Sample the center of the app without the OS status/navigation bars.
        // A white system ANR dialog typically covers > 60% of this region.
        for (int row = 0; row < 5; row++) {
            for (int column = 0; column < 7; column++) {
                int x = Math.round(screenshot.getWidth()
                    * (0.28f + 0.44f * column / 6f));
                int y = Math.round(screenshot.getHeight()
                    * (0.40f + 0.20f * row / 4f));
                int pixel = screenshot.getPixel(x, y);
                int red = Color.red(pixel);
                int green = Color.green(pixel);
                int blue = Color.blue(pixel);
                if (red > 212 && green > 212 && blue > 212
                        && Math.max(red, Math.max(green, blue))
                            - Math.min(red, Math.min(green, blue)) < 20) {
                    paleSamples++;
                }
                totalSamples++;
            }
        }
        assertTrue("Possible bright OS dialog over the dark QA Explorer: "
                + paleSamples + "/" + totalSamples + " pale samples",
            paleSamples < totalSamples * 0.60f);
    }

    @Test public void detectsSyntheticSystemOverlayBeforeEvidenceExport() {
        // Pure pixel regression for the observed API35 Pixel Launcher ANR:
        // a light modal covering the center must fail even with valid pixels.
        Bitmap dark = Bitmap.createBitmap(300, 600, Bitmap.Config.ARGB_8888);
        Bitmap blocked = Bitmap.createBitmap(300, 600, Bitmap.Config.ARGB_8888);
        try {
            dark.eraseColor(Color.BLACK);
            blocked.eraseColor(Color.BLACK);
            Canvas canvas = new Canvas(blocked);
            android.graphics.Paint paint = new android.graphics.Paint();
            paint.setColor(0xfff0eff5);
            canvas.drawRoundRect(40, 195, 260, 405, 18, 18, paint);
            // A launcher ANR may be dismissed once, but only with a
            // precise system label and a real Android close control.
            AccessibilityNodeInfo launcher = AccessibilityNodeInfo.obtain();
            AccessibilityNodeInfo appAnr = AccessibilityNodeInfo.obtain();
            AccessibilityNodeInfo unrelated = AccessibilityNodeInfo.obtain();
            AccessibilityNodeInfo close = AccessibilityNodeInfo.obtain();
            try {
                launcher.setPackageName("android");
                launcher.setText("Pixel Launcher isn't responding");
                appAnr.setPackageName("android");
                appAnr.setText("NegrecoDroid isn't responding");
                unrelated.setPackageName("android");
                unrelated.setText("Camera isn't responding");
                close.setPackageName("android");
                close.setViewIdResourceName("android:id/aerr_close");
                close.setClickable(true);
                // A real failed CI capture reported this exact OS focus.
                String exact = "mCurrentFocus=Window{ec8b92d u0 "
                    + "Application Not Responding: "
                    + "com.google.android.apps.nexuslauncher}\n"
                    + "mFocusedApp=ActivityRecord{153e7 u0 "
                    + "com.google.android.apps.nexuslauncher/"
                    + ".NexusLauncherActivity t7}";
                assertTrue("Exact external-launcher ANR may be recognized",
                    isExactLauncherAnrWindow(exact));
                assertFalse("Unrelated modal cannot be dismissed",
                    isExactLauncherAnrWindow(exact.replace(
                        "Application Not Responding: "
                            + "com.google.android.apps.nexuslauncher}",
                        "Application Not Responding: com.readroid.app}")));
                assertFalse("App ANR cannot be dismissed",
                    isExactLauncherAnrWindow(exact.replace(
                        "com.google.android.apps.nexuslauncher}",
                        "com.readroid.app}")));
                assertFalse("Launcher must actually own focused Activity",
                    isExactLauncherAnrWindow(exact.replace(
                        "com.google.android.apps.nexuslauncher/"
                            + ".NexusLauncherActivity",
                        "com.readroid.app/.MainActivity")));
                assertFalse("Focus evidence may not be incomplete",
                    isExactLauncherAnrWindow(
                        "mCurrentFocus=Window{ec8b92d u0 Application "
                            + "Not Responding: com.google.android.apps."
                            + "nexuslauncher}"));
                assertTrue(isLauncherAnrNode(launcher));
                assertFalse(isLauncherAnrNode(appAnr));
                assertFalse(isLauncherAnrNode(unrelated));
                assertTrue(isAppAnrNode(appAnr));
                assertFalse(isAppAnrNode(launcher));
                assertFalse(isAppAnrNode(unrelated));
                assertTrue(isLauncherCloseNode(close));
                close.setClickable(false);
                assertFalse(isLauncherCloseNode(close));
                close.setClickable(true);
                close.setPackageName("com.readroid.app");
                assertFalse(isLauncherCloseNode(close));
            } finally {
                launcher.recycle();
                appAnr.recycle();
                unrelated.recycle();
                close.recycle();
            }
            assertNoBrightSystemOverlay(dark);
            try {
                assertNoBrightSystemOverlay(blocked);
                fail("A centered system modal was mistakenly approved");
            } catch (AssertionError expected) {
                assertTrue(expected.getMessage()
                    .contains("Possible bright OS dialog"));
            }
        } finally {
            dark.recycle();
            blocked.recycle();
        }
    }

    @Test public void captureRealActivityWithIndexedSyntheticApk() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File apk = File.createTempFile("p7_fixture_", ".apk", context.getCacheDir());
        File index = new File(apk.getAbsolutePath() + ".idx.db");
        try {
            writeFixture(apk);
            byte[] original = Files.readAllBytes(apk.toPath());
            ApkDiskIndex.build(apk, index);
            assertTrue("Synthetic index missing", index.isFile());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        setField(activity, "currentApk", apk);
                        setField(activity, "currentIndex", index);
                        Method display = MainActivity.class.getDeclaredMethod(
                            "displayAnalyzedReport", JSONObject.class);
                        display.setAccessible(true);
                        display.invoke(activity, report(apk));
                        View root = activity.getWindow().getDecorView();
                        View tab = filesTab(root);
                        assertNotNull("Files tab missing", tab);
                        assertTrue(tab.performClick());
                        assertTrue("Files tab not selected", tab.isSelected());
                        assertNotNull(byDescription(root, "Abrir pasta assets/"));
                        assertNotNull(byDescription(root, "Abrir pasta res/"));
                        assertNotNull(byDescription(root, "Abrir arquivo AndroidManifest.xml"));
                    } catch (Exception error) {
                        throw new AssertionError(error);
                    }
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                // The real file rows must be visible, not hidden by an ANR,
                // launcher/system modal or unexpected foreground application.
                assertExplorerWindowInForeground(scenario);
                Bitmap screenshot = InstrumentationRegistry.getInstrumentation()
                    .getUiAutomation().takeScreenshot();
                assertNotNull("Emulator screenshot unavailable", screenshot);
                assertTrue(screenshot.getWidth() > 0 && screenshot.getHeight() > 0);
                try {
                    assertExplorerWindowInForeground(scenario);
                    assertNoBrightSystemOverlay(screenshot);
                } catch (AssertionError blocked) {
                    screenshot.recycle();
                    throw blocked;
                }
                try (FileOutputStream out =
                        context.openFileOutput(SCREENSHOT, Context.MODE_PRIVATE)) {
                    assertTrue("PNG compression failed", screenshot.compress(
                        Bitmap.CompressFormat.PNG, 100, out));
                } finally {
                    screenshot.recycle();
                }
                assertTrue("Saved screenshot missing",
                    new File(context.getFilesDir(), SCREENSHOT).length() > 1024);
                assertArrayEquals("Source ZIP changed after capture", original,
                    Files.readAllBytes(apk.toPath()));
            }
        } finally {
            SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }
}
