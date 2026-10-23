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
     * A valid PNG may still contain an Android ANR modal over the real app.
     * Keep this test screenshot honest: check the focused accessibility
     * window AND a near-white centered rectangle characteristic of system
     * ANR dialogs in our isolated, dark-theme fixture. This is not a general
     * image classifier and does not certify visual fidelity.
     */
    private static void assertExplorerWindowInForeground() {
        AccessibilityNodeInfo active = InstrumentationRegistry
            .getInstrumentation().getUiAutomation().getRootInActiveWindow();
        assertNotNull("No active accessibility window before capture", active);
        try {
            CharSequence owner = active.getPackageName();
            assertEquals("A system window obscures the Explorer",
                "com.readroid.app",
                owner == null ? null : owner.toString());
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
                assertExplorerWindowInForeground();
                Bitmap screenshot = InstrumentationRegistry.getInstrumentation()
                    .getUiAutomation().takeScreenshot();
                assertNotNull("Emulator screenshot unavailable", screenshot);
                assertTrue(screenshot.getWidth() > 0 && screenshot.getHeight() > 0);
                try {
                    assertExplorerWindowInForeground();
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
