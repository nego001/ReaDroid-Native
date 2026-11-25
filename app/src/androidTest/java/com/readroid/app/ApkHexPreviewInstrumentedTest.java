package com.readroid.app;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;
import org.json.JSONArray;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ApkHexPreviewInstrumentedTest {
    private static final String PATH = "assets/sample.bin";

    private static File archive(byte[] data) throws IOException {
        File file = File.createTempFile("hex_preview_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(file.toPath()))) {
            zip.putNextEntry(new ZipEntry(PATH));
            zip.write(data);
            zip.closeEntry();
        } catch (IOException failure) {
            file.delete();
            throw failure;
        }
        return file;
    }

    @Test public void exactHexOffsetsAndAscii() throws Exception {
        byte[] bytes = new byte[17];
        bytes[0] = 65; bytes[1] = 32; bytes[2] = (byte) 255; bytes[16] = 90;
        File apk = archive(bytes);
        try {
            String before = ApkIntegrity.sha256(apk);
            ApkHexPreview.Result r = ApkHexPreview.read(apk, PATH);
            assertEquals(17, r.shown);
            assertEquals(17L, r.size);
            assertFalse(r.truncated);
            assertTrue(r.dump.startsWith("00000000  41 20 FF 00"));
            assertTrue(r.dump.contains("|A ..............|"));
            assertTrue(r.dump.contains("00000010  5A "));
            assertTrue(r.dump.endsWith("|Z|\n"));
            assertEquals(before, ApkIntegrity.sha256(apk));
        } finally { apk.delete(); }
    }

    @Test public void largeEntryIsBoundedAndExplicitlyPartial() throws Exception {
        File apk = archive(new byte[100000]);
        try {
            ApkHexPreview.Result r = ApkHexPreview.read(apk, PATH);
            assertTrue(r.truncated);
            assertEquals(100000L, r.size);
            assertEquals(ApkHexPreview.MAX_BYTES, r.shown);
            assertTrue(r.dump.contains("00000FF0"));
            assertFalse(r.dump.contains("00001000"));
        } finally { apk.delete(); }
    }

    @Test public void emptyEntryIsNotAnError() throws Exception {
        File apk = archive(new byte[0]);
        try {
            ApkHexPreview.Result r = ApkHexPreview.read(apk, PATH);
            assertFalse(r.truncated);
            assertEquals(0, r.shown);
            assertEquals("", r.dump);
        } finally { apk.delete(); }
    }

    @Test public void invalidOrMissingPathRejected() throws Exception {
        File apk = archive(new byte[]{1});
        try {
            for (String path : new String[]{"../sample.bin", "/assets/sample.bin", "absent.bin"}) {
                try {
                    ApkHexPreview.read(apk, path);
                    fail("Expected rejection for " + path);
                } catch (IOException expected) { assertNotNull(expected.getMessage()); }
            }
        } finally { apk.delete(); }
    }

    @Test public void actualHexMenuDisplaysBytesWithoutChangingPlan() throws Exception {
        File apk = archive(new byte[]{65, 66, 67});
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> {
                try {
                    java.lang.reflect.Field field = MainActivity.class.getDeclaredField("explorerView");
                    field.setAccessible(true);
                    ExplorerView explorer = (ExplorerView) field.get(a);
                    explorer.setFiles(new JSONArray(), apk);
                    java.lang.reflect.Method menu = ExplorerView.class.getDeclaredMethod(
                        "showFileActions", String.class, String.class, String.class, long.class, boolean.class);
                    menu.setAccessible(true);
                    menu.invoke(explorer, "sample.bin", PATH, "Outros", 3L, false);
                } catch (Exception failure) { throw new AssertionError(failure); }
            });
            UiDevice device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
            UiObject2 action = device.wait(Until.findObject(By.text("Ver hexadecimal")), 10000);
            assertNotNull(action);
            action.click();
            assertNotNull(device.wait(Until.findObject(By.text("Prévia hexadecimal")), 10000));
            assertNotNull(device.wait(Until.findObject(By.textContains("00000000  41 42 43")), 10000));
            assertNotNull(device.wait(Until.findObject(By.textContains("3 de 3 bytes")), 10000));
            device.pressBack();
            scenario.onActivity(a -> {
                try {
                    java.lang.reflect.Field field = MainActivity.class.getDeclaredField("explorerView");
                    field.setAccessible(true);
                    assertEquals(0, ((ExplorerView) field.get(a)).getEditPlan().size());
                } catch (Exception failure) { throw new AssertionError(failure); }
            });
        } finally { apk.delete(); }
    }
}
