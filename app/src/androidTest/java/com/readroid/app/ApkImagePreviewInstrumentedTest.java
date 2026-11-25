package com.readroid.app;

import android.graphics.Bitmap;
import android.graphics.Color;
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
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ApkImagePreviewInstrumentedTest {
    private static final String PATH = "assets/preview.png";

    private static byte[] raster(int width, int height, Bitmap.CompressFormat format) {
        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        try {
            bitmap.eraseColor(Color.RED);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            assertTrue(bitmap.compress(format, 90, out));
            return out.toByteArray();
        } finally { bitmap.recycle(); }
    }

    private static File archive(String path, byte[] data) throws IOException {
        File file = File.createTempFile("image_preview_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(file.toPath()))) {
            zip.putNextEntry(new ZipEntry(path));
            zip.write(data);
            zip.closeEntry();
        } catch (IOException failure) {
            file.delete();
            throw failure;
        }
        return file;
    }

    @Test public void pngPreviewPreservesSourceAndRealDimensions() throws Exception {
        File apk = archive(PATH, raster(2048, 512, Bitmap.CompressFormat.PNG));
        try {
            String before = ApkIntegrity.sha256(apk);
            ApkImagePreview.Result r = ApkImagePreview.read(apk, PATH);
            try {
                assertEquals(2048, r.width);
                assertEquals(512, r.height);
                assertEquals(1024, r.bitmap.getWidth());
                assertEquals(256, r.bitmap.getHeight());
                assertEquals(Color.RED, r.bitmap.getPixel(0, 0));
                assertEquals("image/png", r.mime);
            } finally { r.bitmap.recycle(); }
            assertEquals(before, ApkIntegrity.sha256(apk));
        } finally { apk.delete(); }
    }

    @Test public void jpegAndWebpAreDecoded() throws Exception {
        String[] paths = {"assets/a.JPG", "assets/b.webp"};
        Bitmap.CompressFormat[] formats = {Bitmap.CompressFormat.JPEG, Bitmap.CompressFormat.WEBP};
        String[] mimes = {"image/jpeg", "image/webp"};
        for (int i = 0; i < paths.length; i++) {
            File apk = archive(paths[i], raster(48, 32, formats[i]));
            try {
                ApkImagePreview.Result r = ApkImagePreview.read(apk, paths[i]);
                try {
                    assertEquals(mimes[i], r.mime);
                    assertEquals(48, r.bitmap.getWidth());
                    assertEquals(32, r.bitmap.getHeight());
                } finally { r.bitmap.recycle(); }
            } finally { apk.delete(); }
        }
    }

    private static void reject(File apk, String path) throws Exception {
        try {
            ApkImagePreview.Result result = ApkImagePreview.read(apk, path);
            result.bitmap.recycle();
            fail("Invalid or over-budget image must be rejected");
        } catch (IOException expected) { assertNotNull(expected.getMessage()); }
        finally { apk.delete(); }
    }

    @Test public void rejectsWrongFormatAndInvalidBytes() throws Exception {
        reject(archive(PATH, raster(16, 16, Bitmap.CompressFormat.JPEG)), PATH);
        reject(archive(PATH, new byte[]{1, 2, 3}), PATH);
        assertFalse(ApkImagePreview.supports("assets/vector.svg"));
        assertFalse(ApkImagePreview.supports("assets/animated.gif"));
    }

    @Test public void rejectsEncodedAndDimensionBudgets() throws Exception {
        reject(archive(PATH, new byte[ApkImagePreview.MAX_ENCODED_BYTES + 1]), PATH);
        reject(archive(PATH, raster(8193, 1, Bitmap.CompressFormat.PNG)), PATH);
    }

    @Test public void actualImageActionShowsNativePreviewWithoutEditing() throws Exception {
        File apk = archive(PATH, raster(64, 32, Bitmap.CompressFormat.PNG));
        String before = ApkIntegrity.sha256(apk);
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
                    menu.invoke(explorer, "preview.png", PATH, "Imagens", 100L, false);
                } catch (Exception failure) { throw new AssertionError(failure); }
            });
            UiDevice device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
            UiObject2 action = device.wait(Until.findObject(By.text("Visualizar imagem")), 10000);
            assertNotNull("Native image action missing", action);
            action.click();
            assertNotNull(device.wait(Until.findObject(By.text("Prévia da imagem")), 10000));
            assertNotNull(device.wait(Until.findObject(By.desc("Imagem do APK: " + PATH)), 10000));
            assertNotNull(device.wait(Until.findObject(By.textContains("64 × 32 px")), 10000));
            device.pressBack();
            scenario.onActivity(a -> {
                try {
                    java.lang.reflect.Field field = MainActivity.class.getDeclaredField("explorerView");
                    field.setAccessible(true);
                    assertEquals(0, ((ExplorerView) field.get(a)).getEditPlan().size());
                } catch (Exception failure) { throw new AssertionError(failure); }
            });
            assertEquals(before, ApkIntegrity.sha256(apk));
        } finally { apk.delete(); }
    }
}
