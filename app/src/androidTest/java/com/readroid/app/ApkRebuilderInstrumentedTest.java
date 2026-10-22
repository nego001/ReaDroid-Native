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
            assertTrue(RebuildVerifier.verifyAgainstOriginal(original, output, edit.snapshot())
                .contains("arquivo(s) não editado(s) conferido(s)"));
            assertTrue(SigningPreflight.inspect(output).contains("Pré-verificação estrutural aprovada"));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void missingEditPathFailsWithoutChangingExistingOutput() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] previous = utf8("Exportação anterior válida: não substituir em caso de falha");
            Files.write(output.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/missing.json", "{\"invalid\":true}");
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot());
                fail("Missing ZIP entry should reject rebuild");
            } catch (IOException expected) {
                assertArrayEquals("Previous output must survive failed rebuild",
                    previous, Files.readAllBytes(output.toPath()));
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
            byte[] previous = utf8("Exportação anterior intacta");
            Files.write(output.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{}");
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot());
                fail("Unsafe ZIP path should be rejected");
            } catch (IOException expected) {
                assertArrayEquals("Unsafe ZIP cannot destroy previous output",
                    previous, Files.readAllBytes(output.toPath()));
                assertTrue("Original must be left intact", original.isFile());
            }
        } finally {
            original.delete();
            output.delete();
        }
    }


    @Test public void comparisonDetectsTamperedUntouchedEntryEvenWhenEditLooksCorrect()
            throws Exception {
        File original = file(".apk");
        File rebuilt = file(".apk");
        try {
            fixture(original, false);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"message\":\"alterado\"}");
            // Construct a ZIP with the correct edited file and manifest/DEX,
            // but corrupt the untouched binary without warning the edit plan.
            try (ZipOutputStream out = new ZipOutputStream(
                    Files.newOutputStream(rebuilt.toPath()))) {
                add(out, "AndroidManifest.xml", utf8("binary manifest placeholder"));
                add(out, "classes.dex", new byte[]{100, 101, 120, 10, 0, 0, 0});
                add(out, "assets/config.json", utf8("{\"message\":\"alterado\"}"));
                add(out, "assets/original.bin", new byte[]{99, 3, 8, -1, 16});
            }
            assertTrue("Edit-only verifier cannot detect unrelated corruption",
                RebuildVerifier.verify(rebuilt, plan.snapshot()).contains("1 alteração"));
            try {
                RebuildVerifier.verifyAgainstOriginal(original, rebuilt, plan.snapshot());
                fail("The untouched binary must match its original SHA-256");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("não editado"));
            }
        } finally {
            original.delete();
            rebuilt.delete();
        }
    }

    @Test public void comparisonDetectsUnexpectedNewEntries() throws Exception {
        File original = file(".apk");
        File rebuilt = file(".apk");
        try {
            fixture(original, false);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"message\":\"novo\"}");
            try (ZipOutputStream out = new ZipOutputStream(
                    Files.newOutputStream(rebuilt.toPath()))) {
                add(out, "AndroidManifest.xml", utf8("binary manifest placeholder"));
                add(out, "classes.dex", new byte[]{100, 101, 120, 10, 0, 0, 0});
                add(out, "assets/config.json", utf8("{\"message\":\"novo\"}"));
                add(out, "assets/original.bin", new byte[]{0, 3, 8, -1, 16});
                add(out, "assets/injected.bin", new byte[]{1, 2});
            }
            try {
                RebuildVerifier.verifyAgainstOriginal(original, rebuilt, plan.snapshot());
                fail("A new file outside the edit plan must be rejected");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("inesperado"));
            }
        } finally {
            original.delete();
            rebuilt.delete();
        }
    }

    @Test public void sourceHashCheckRejectsUnexpectedOriginalMutation() throws Exception {
        File original = file(".apk");
        try {
            fixture(original, false);
            String checksum = ApkIntegrity.sha256(original);
            assertEquals(64, checksum.length());
            ApkIntegrity.confirmExpected(original, checksum);
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(original, true)) {
                out.write(0x55);
            }
            try {
                ApkIntegrity.confirmExpected(original, checksum);
                fail("A changed source must be detected before export");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("não confere"));
            }
        } finally {
            original.delete();
        }
    }

    @Test public void directMapCannotBypassUtf8ByteLimit() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] immutable = Files.readAllBytes(original.toPath());
            assertTrue(output.delete());
            char[] chars = new char[44000];
            java.util.Arrays.fill(chars, '界'); // 132000 UTF-8 bytes
            Map<String, String> raw = Collections.singletonMap(
                "assets/config.json", new String(chars));
            try {
                ApkRebuilder.rebuild(original, output, raw);
                fail("Direct rebuild must obey EditPlan's byte budget");
            } catch (IOException expected) {
                assertFalse("Must reject before creating output", output.exists());
            }
            assertArrayEquals(immutable, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void directMapRejectsOrphanSurrogatesBeforeOutput() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] immutable = Files.readAllBytes(original.toPath());
            assertTrue(output.delete());
            String malformed = "abc" + (char) 0xD83D;
            Map<String, String> raw = Collections.singletonMap(
                "assets/config.json", malformed);
            try {
                ApkRebuilder.rebuild(original, output, raw);
                fail("Direct rebuild must not replace malformed Unicode with '?'");
            } catch (IOException expected) {
                assertFalse("Must reject before creating output", output.exists());
            }
            assertArrayEquals(immutable, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void validatedSnapshotIgnoresInconsistentCallerMap() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            Map<String, String> deceptive = new java.util.AbstractMap<String, String>() {
                @Override public java.util.Set<Map.Entry<String, String>> entrySet() {
                    return Collections.<Map.Entry<String, String>>singleton(
                        new java.util.AbstractMap.SimpleImmutableEntry<>(
                            "assets/config.json", "validado"));
                }
                @Override public String get(Object path) {
                    return "não foi validado";
                }
            };
            ApkRebuilder.rebuild(original, output, deceptive);
            try (ZipFile rebuilt = new ZipFile(output)) {
                assertArrayEquals(utf8("validado"), entryBytes(rebuilt, "assets/config.json"));
            }
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void interruptedRebuildKeepsPriorExportAndSource() throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] source = Files.readAllBytes(original.toPath());
            byte[] previous = utf8("arquivo de destino anterior");
            Files.write(output.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{}");
            Thread.currentThread().interrupt();
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot());
                fail("Interrupted rebuild must refuse committing the destination");
            } catch (java.io.InterruptedIOException expected) {
                // Do not publish a partial archive after cancellation.
            } finally {
                Thread.interrupted(); // Clear only the flag set by this test.
            }
            assertArrayEquals(previous, Files.readAllBytes(output.toPath()));
            assertArrayEquals(source, Files.readAllBytes(original.toPath()));
        } finally {
            Thread.interrupted();
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
