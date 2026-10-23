package com.readroid.app;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Bitmap;
import android.os.ParcelFileDescriptor;
import java.io.FileInputStream;
import java.io.InputStream;
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
                Bitmap screenshot = InstrumentationRegistry.getInstrumentation()
                    .getUiAutomation().takeScreenshot();
                assertNotNull("Emulator screenshot unavailable", screenshot);
                assertTrue(screenshot.getWidth() > 0 && screenshot.getHeight() > 0);
                try (FileOutputStream out =
                        context.openFileOutput(SCREENSHOT, Context.MODE_PRIVATE)) {
                    assertTrue("PNG compression failed", screenshot.compress(
                        Bitmap.CompressFormat.PNG, 100, out));
                } finally {
                    screenshot.recycle();
                }
                assertTrue("Saved screenshot missing",
                    new File(context.getFilesDir(), SCREENSHOT).length() > 1024);
                // Gradle removes the debug app after instrumentation, wiping
                // its private files. Persist a second real Android capture in
                // emulator Download via the test-only shell identity.
                // No app permission or public-device data is accessed.
                ParcelFileDescriptor pipe = InstrumentationRegistry
                    .getInstrumentation().getUiAutomation().executeShellCommand(
                        "sh -c 'mkdir -p /sdcard/Download && screencap -p " +
                        "/sdcard/Download/p7-explorer-populated.png'");
                assertNotNull("Shell screenshot pipe unavailable", pipe);
                try (ParcelFileDescriptor descriptor = pipe;
                        InputStream result = new FileInputStream(
                            descriptor.getFileDescriptor())) {
                    byte[] buffer = new byte[1024];
                    while (result.read(buffer) != -1) { /* wait for shell exit */ }
                }
                assertArrayEquals("Source ZIP changed after capture", original,
                    Files.readAllBytes(apk.toPath()));
            }
        } finally {
            SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }
}
