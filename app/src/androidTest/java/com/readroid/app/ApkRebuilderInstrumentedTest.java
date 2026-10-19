package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Collections;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Checks experimental unsigned ZIP rebuild. Does not claim APK installability. */
@RunWith(AndroidJUnit4.class)
public final class ApkRebuilderInstrumentedTest {
    private File file(String suffix) throws IOException {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return File.createTempFile("v3_rebuild_test_", suffix, ctx.getCacheDir());
    }

    private static void add(ZipOutputStream out, String path, byte[] data) throws IOException {
        ZipEntry item = new ZipEntry(path);
        out.putNextEntry(item);
        out.write(data);
        out.closeEntry();
    }

    private static byte[] utf8(String text) {
        return text.getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] entryBytes(ZipFile archive, String path) throws IOException {
        ZipEntry item = archive.getEntry(path);
        assertNotNull(path, item);
        try (InputStream input = archive.getInputStream(item);
             ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int n;
            while ((n = input.read(buffer)) != -1) bytes.write(buffer, 0, n);
            return bytes.toByteArray();
        }
    }

    private static void fixture(File destination, boolean unsafe) throws Exception {
        try (ZipOutputStream out = new ZipOutputStream(Files.newOutputStream(destination.toPath()))) {
            add(out, "AndroidManifest.xml", utf8("binary manifest placeholder"));
            add(out, "classes.dex", new byte[]{100, 101, 120, 10, 0, 0, 0});
            add(out, "assets/config.json", utf8("{\"message\":\"original\"}"));
            add(out, "assets/original.bin", new byte[]{0, 3, 8, -1, 16});
            add(out, "META-INF/CERT.RSA", new byte[]{1, 2, 3});
            add(out, "META-INF/CERT.SF", utf8("old signature"));
            add(out, "META-INF/MANIFEST.MF", utf8("old checksums"));
            if (unsafe) add(out, "../path-traversal.txt", utf8("unsafe"));
        }
    }

    @Test public void rebuildChangesOnlySelectedTextPreservesOriginalAndDropsOldSignatures()
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] immutableOriginal = Files.readAllBytes(original.toPath());
            EditPlan edit = new EditPlan();
            String text = "{\"message\":\"alterado ✓\"}";
            edit.addTextReplacement("assets/config.json", text);
            ApkRebuilder.rebuild(original, output, edit.snapshot());
            assertArrayEquals(immutableOriginal, Files.readAllBytes(original.toPath()));
            try (ZipFile rebuilt = new ZipFile(output)) {
                assertEquals(text, new String(entryBytes(rebuilt, "assets/config.json"),
                    StandardCharsets.UTF_8));
                assertArrayEquals(new byte[]{0, 3, 8, -1, 16},
                    entryBytes(rebuilt, "assets/original.bin"));
                assertNull(rebuilt.getEntry("META-INF/CERT.RSA"));
                assertNull(rebuilt.getEntry("META-INF/CERT.SF"));
                assertNull(rebuilt.getEntry("META-INF/MANIFEST.MF"));
            }
            assertTrue(RebuildVerifier.verify(output, edit.snapshot()).contains("1 alteração"));
            assertTrue(SigningPreflight.inspect(output).contains("Pré-verificação estrutural aprovada"));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void missingEditPathFailsAndDeletesIncompleteOutput() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/missing.json", "{\"invalid\":true}");
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot());
                fail("Missing ZIP entry should reject rebuild");
            } catch (IOException expected) {
                assertFalse("Incomplete output must be deleted", output.exists());
                assertTrue("Original ZIP must remain", original.isFile());
            }
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void traversalEntryIsBlockedWithoutChangingOriginal() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, true);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{}");
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot());
                fail("Unsafe ZIP path should be rejected");
            } catch (IOException expected) {
                assertFalse("Partial output must be deleted", output.exists());
                assertTrue("Original must be left intact", original.isFile());
            }
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void cannotOverwriteSourceApk() throws Exception {
        File original = file(".apk");
        try {
            fixture(original, false);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{}");
            try {
                ApkRebuilder.rebuild(original, original, plan.snapshot());
                fail("Source APK overwrite must be blocked");
            } catch (IOException expected) {
                assertTrue(original.length() > 0);
            }
        } finally {
            original.delete();
        }
    }
}
