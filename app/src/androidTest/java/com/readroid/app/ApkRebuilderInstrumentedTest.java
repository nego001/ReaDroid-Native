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


    /** A path rejected by admission must also be rejected by direct rebuild. */
    private void assertDirectRebuildRejectsPath(String untrustedPath)
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            try (ZipOutputStream out = new ZipOutputStream(
                    Files.newOutputStream(original.toPath()))) {
                add(out, "AndroidManifest.xml", utf8("binary manifest placeholder"));
                add(out, "classes.dex", new byte[]{100, 101, 120, 10});
                add(out, "assets/config.json", utf8("{\"safe\":true}"));
                add(out, untrustedPath, utf8("untrusted path"));
            }
            byte[] source = Files.readAllBytes(original.toPath());
            byte[] previous = utf8("previous export must remain intact");
            Files.write(output.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"safe\":false}");
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot());
                fail("Direct rebuild must reject unsafe path: " + untrustedPath);
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
            assertArrayEquals(previous, Files.readAllBytes(output.toPath()));
            assertArrayEquals(source, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void directRebuildRejectsDotSegmentsAndRepeatedSeparators()
            throws Exception {
        assertDirectRebuildRejectsPath("assets/./payload.bin");
        assertDirectRebuildRejectsPath("assets//payload.bin");
    }

    @Test public void directRebuildRejectsOverlongAndTooDeepPaths()
            throws Exception {
        StringBuilder longName = new StringBuilder("assets/");
        for (int i = 0; i < 4200; i++) longName.append('x');
        longName.append(".txt");
        assertDirectRebuildRejectsPath(longName.toString());

        StringBuilder deepPath = new StringBuilder();
        for (int i = 0; i < 130; i++) deepPath.append("dir/");
        deepPath.append("payload.bin");
        assertDirectRebuildRejectsPath(deepPath.toString());
    }

    @Test public void directVerifierRejectsInvalidPathDespiteValidEditedContent()
            throws Exception {
        File output = file(".apk");
        try {
            try (ZipOutputStream out = new ZipOutputStream(
                    Files.newOutputStream(output.toPath()))) {
                add(out, "AndroidManifest.xml", utf8("manifest"));
                add(out, "classes.dex", utf8("dex"));
                add(out, "assets/config.json", utf8("{\"new\":1}"));
                add(out, "assets/./danger.bin", utf8("extra"));
            }
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"new\":1}");
            try {
                RebuildVerifier.verify(output, plan.snapshot());
                fail("Verifier cannot claim success with unsafe ZIP path");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
        } finally {
            output.delete();
        }
    }

    @Test public void legitimateDoubleDotsInsideBasenameRemainValid()
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            try (ZipOutputStream out = new ZipOutputStream(
                    Files.newOutputStream(original.toPath()))) {
                add(out, "AndroidManifest.xml", utf8("manifest"));
                add(out, "classes.dex", utf8("dex"));
                add(out, "assets/config.json", utf8("{\"old\":1}"));
                add(out, "assets/a..b.txt", utf8("dots within basename"));
            }
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"new\":1}");
            ApkRebuilder.rebuild(original, output, plan.snapshot());
            assertTrue(RebuildVerifier.verify(output, plan.snapshot())
                .contains("1 alteração"));
            try (ZipFile zip = new ZipFile(output)) {
                assertEquals("dots within basename",
                    new String(entryBytes(zip, "assets/a..b.txt"), StandardCharsets.UTF_8));
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


    @Test public void damagedStagingZipNeverOverwritesPreviousExport()
            throws Exception {
        File original = file(".apk");
        File target = file(".apk");
        try {
            fixture(original, false);
            byte[] sourceBytes = Files.readAllBytes(original.toPath());
            byte[] previous = utf8("valid previous export");
            Files.write(target.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"new\":true}");
            try {
                ApkRebuilder.rebuild(original, target, plan.snapshot(),
                    staged -> Files.write(staged.toPath(), utf8("broken staged ZIP")));
                fail("Corrupted staging archive must be rejected before atomic move");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
            assertArrayEquals(previous, Files.readAllBytes(target.toPath()));
            assertArrayEquals(sourceBytes, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            target.delete();
        }
    }

    @Test public void validButTamperedStagingMemberCannotReplacePreviousExport()
            throws Exception {
        File original = file(".apk");
        File target = file(".apk");
        try {
            fixture(original, false);
            byte[] sourceBytes = Files.readAllBytes(original.toPath());
            byte[] previous = utf8("validated previous result");
            Files.write(target.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"edited\":true}");
            try {
                ApkRebuilder.rebuild(original, target, plan.snapshot(), staged -> {
                    File alternate = File.createTempFile("f110_tamper_", ".zip",
                        staged.getParentFile());
                    try {
                        try (ZipFile input = new ZipFile(staged);
                             ZipOutputStream out = new ZipOutputStream(
                                Files.newOutputStream(alternate.toPath()))) {
                            java.util.Enumeration<? extends ZipEntry> cursor = input.entries();
                            while (cursor.hasMoreElements()) {
                                ZipEntry entry = cursor.nextElement();
                                if (entry.isDirectory()) {
                                    out.putNextEntry(new ZipEntry(entry.getName()));
                                    out.closeEntry();
                                    continue;
                                }
                                byte[] payload = entryBytes(input, entry.getName());
                                if ("assets/original.bin".equals(entry.getName()))
                                    payload[0] ^= 1;
                                add(out, entry.getName(), payload);
                            }
                        }
                        Files.copy(alternate.toPath(), staged.toPath(),
                            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    } finally { alternate.delete(); }
                });
                fail("A valid ZIP with an altered untouched member must fail");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("não editado"));
            }
            assertArrayEquals(previous, Files.readAllBytes(target.toPath()));
            assertArrayEquals(sourceBytes, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            target.delete();
        }
    }

    @Test public void canceledAtStagedVerificationBoundaryKeepsPreviousResult()
            throws Exception {
        File original = file(".apk");
        File target = file(".apk");
        try {
            fixture(original, false);
            byte[] previous = utf8("previous result remains available");
            Files.write(target.toPath(), previous);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"edited\":true}");
            try {
                ApkRebuilder.rebuild(original, target, plan.snapshot(),
                    staged -> Thread.currentThread().interrupt());
                fail("Cancellation after staging must block publication");
            } catch (java.io.InterruptedIOException expected) {
                assertNotNull(expected.getMessage());
            } finally { Thread.interrupted(); }
            assertArrayEquals(previous, Files.readAllBytes(target.toPath()));
        } finally {
            Thread.interrupted();
            original.delete();
            target.delete();
        }
    }

    @Test public void verifiedStagingAtomicallyReplacesPriorExport()
            throws Exception {
        File original = file(".apk");
        File target = file(".apk");
        try {
            fixture(original, false);
            byte[] sourceBytes = Files.readAllBytes(original.toPath());
            Files.write(target.toPath(), utf8("old export"));
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"committed\":true}");
            ApkRebuilder.rebuild(original, target, plan.snapshot());
            assertTrue(RebuildVerifier.verifyAgainstOriginal(original, target,
                plan.snapshot()).contains("arquivo(s) não editado(s)"));
            assertArrayEquals(sourceBytes, Files.readAllBytes(original.toPath()));
            try (ZipFile zip = new ZipFile(target)) {
                assertEquals("{\"committed\":true}", new String(
                    entryBytes(zip, "assets/config.json"), StandardCharsets.UTF_8));
            }
        } finally {
            original.delete();
            target.delete();
        }
    }

    @Test public void lowSpaceAfterStagingPreservesOldExportAndOriginal()
            throws Exception {
        File original = file(".apk");
        File target = file(".apk");
        try {
            fixture(original, false);
            byte[] before = Files.readAllBytes(original.toPath());
            byte[] prior = utf8("previous signed-off export must survive");
            Files.write(target.toPath(), prior);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"edited\":1}");
            java.util.concurrent.atomic.AtomicInteger reads =
                new java.util.concurrent.atomic.AtomicInteger();
            try {
                ApkRebuilder.rebuild(original, target, plan.snapshot(), staged -> {},
                    () -> reads.incrementAndGet() >= 4
                        ? 32L * 1024 * 1024
                        : 512L * 1024 * 1024);
                fail("Low storage after staging cannot commit");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Espaço insuficiente"));
            }
            assertArrayEquals(prior, Files.readAllBytes(target.toPath()));
            assertArrayEquals(before, Files.readAllBytes(original.toPath()));
            assertTrue("Space probes must happen before and after staging",
                reads.get() >= 4);
        } finally {
            original.delete();
            target.delete();
        }
    }

    @Test public void f115InvalidationDuringZipCopyAbortsAndPreservesPreviousExport()
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] source = Files.readAllBytes(original.toPath());
            byte[] prior = utf8("previous completed export");
            Files.write(output.toPath(), prior);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"new\":true}");
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token token = guard.begin();
            java.util.concurrent.atomic.AtomicInteger chunks =
                new java.util.concurrent.atomic.AtomicInteger();
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot(),
                    staged -> {}, () -> 512L * 1024 * 1024, token,
                    (path, total) -> {
                        chunks.incrementAndGet();
                        guard.invalidate();
                    });
                fail("Stale project must never replace the prior export");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            assertTrue("Must have begun copying ZIP content", chunks.get() > 0);
            assertArrayEquals(prior, Files.readAllBytes(output.toPath()));
            assertArrayEquals(source, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void f115CancellationAtVerificationBoundaryPreservesPriorExport()
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] prior = utf8("prior output");
            Files.write(output.toPath(), prior);
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{}");
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token token = guard.begin();
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot(),
                    staged -> guard.invalidate(), () -> 512L * 1024 * 1024,
                    token, (path, total) -> {});
                fail("Cancelled staging must never reach atomic commit");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            assertArrayEquals(prior, Files.readAllBytes(output.toPath()));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void f115AlreadyRevokedTokenNeverCreatesResult()
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            assertTrue(output.delete());
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token stale = guard.begin();
            guard.invalidate();
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{}");
            try {
                ApkRebuilder.rebuild(original, output, plan.snapshot(), stale);
                fail("Stale export cannot start");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            assertFalse(output.exists());
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void f115CurrentTokenCanBuildAndVerifyValidZip()
            throws Exception {
        File original = file(".apk");
        File output = file(".apk");
        try {
            fixture(original, false);
            byte[] source = Files.readAllBytes(original.toPath());
            EditPlan plan = new EditPlan();
            plan.addTextReplacement("assets/config.json", "{\"ok\":true}");
            ExportSessionGuard.Token active = new ExportSessionGuard().begin();
            ApkRebuilder.rebuild(original, output, plan.snapshot(), active);
            assertTrue(RebuildVerifier.verifyAgainstOriginal(
                original, output, plan.snapshot(), active).contains("conferido(s)"));
            assertArrayEquals(source, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            output.delete();
        }
    }

    @Test public void f115RevokedTokenRejectsShaCrcAndRebuildVerifier()
            throws Exception {
        File original = file(".apk");
        try {
            fixture(original, false);
            ExportSessionGuard guard = new ExportSessionGuard();
            ExportSessionGuard.Token stale = guard.begin();
            guard.invalidate();
            try {
                ApkIntegrity.sha256(original, stale);
                fail("Revoked SHA must abort");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            try {
                ApkZipIntegrity.verify(original, stale);
                fail("Revoked CRC audit must abort");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            try {
                RebuildVerifier.verify(original,
                    Collections.singletonMap("assets/config.json", "{}"), stale);
                fail("Revoked verifier must abort");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
        } finally { original.delete(); }
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
