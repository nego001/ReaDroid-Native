package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ImportConcurrencyInstrumentedTest {
    private static final long AVAILABLE = 192L * 1024 * 1024;

    private static File testDirectory() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return Files.createTempDirectory(context.getCacheDir().toPath(),
            "f122_concurrency_").toFile();
    }

    private static File oldProject(File root) throws Exception {
        File prior = new File(root, "previous_user_project.apk");
        Files.write(prior.toPath(), "previous project and unsaved edits"
            .getBytes(StandardCharsets.UTF_8));
        return prior;
    }

    private static void assertOnlyOriginal(File root, File old) throws Exception {
        assertTrue(old.isFile());
        assertEquals("previous project and unsaved edits",
            new String(Files.readAllBytes(old.toPath()), StandardCharsets.UTF_8));
        File[] files = root.listFiles();
        assertNotNull(files);
        assertEquals("Stale import left private candidate behind", 1, files.length);
        assertEquals(old.getCanonicalPath(), files[0].getCanonicalPath());
    }

    private static void deleteAll(File root) {
        if (root == null) return;
        File[] children = root.listFiles();
        if (children != null) for (File child : children) child.delete();
        root.delete();
    }

    private static File simpleZip(File root) throws Exception {
        File original = new File(root, "synthetic_untrusted.zip");
        try (ZipOutputStream out = new ZipOutputStream(Files.newOutputStream(original.toPath()))) {
            out.putNextEntry(new ZipEntry("AndroidManifest.xml"));
            out.write(new byte[]{1,2,3,4});
            out.closeEntry();
            out.putNextEntry(new ZipEntry("classes.dex"));
            out.write(new byte[]{100,101,120,10,0,0,0});
            out.closeEntry();
        }
        return original;
    }

    @Test public void f122SupersededRequestCannotOpenProviderOrCreateCache()
            throws Exception {
        File root = testDirectory();
        try {
            File prior = oldProject(root);
            ExportSessionGuard generations = new ExportSessionGuard();
            ExportSessionGuard.Token stale = generations.begin();
            generations.begin(); // Latest user selection wins.
            AtomicInteger opened = new AtomicInteger();
            try {
                ApkImportStaging.copy(root, () -> {
                    opened.incrementAndGet();
                    return new ByteArrayInputStream(new byte[]{1});
                }, () -> AVAILABLE, stale);
                fail("Outdated import may not contact SAF provider");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("cancelada"));
            }
            assertEquals(0, opened.get());
            assertOnlyOriginal(root, prior);
        } finally { deleteAll(root); }
    }

    @Test public void f122NewRequestDuringOldReadCancelsOldAndAcceptsNewCopy()
            throws Exception {
        File root = testDirectory();
        try {
            File prior = oldProject(root);
            ExportSessionGuard generations = new ExportSessionGuard();
            ExportSessionGuard.Token first = generations.begin();
            final ExportSessionGuard.Token[] second = {null};
            byte[] oldBytes = new byte[4096];
            InputStream source = new ByteArrayInputStream(oldBytes) {
                boolean switched;
                @Override public synchronized int read(byte[] b, int offset, int length) {
                    int read = super.read(b, offset, Math.min(length, 512));
                    if (!switched) {
                        switched = true;
                        second[0] = generations.begin(); // New project chosen mid-read.
                    }
                    return read;
                }
            };
            try {
                ApkImportStaging.copy(root, () -> source, () -> AVAILABLE, first);
                fail("Superseded SAF worker must not complete stale copy");
            } catch (InterruptedIOException expected) {
                assertFalse(first.isActive());
            }
            assertOnlyOriginal(root, prior);
            assertNotNull(second[0]);
            byte[] newBytes = "most recently selected APK".getBytes(StandardCharsets.UTF_8);
            ApkImportStaging.Result active = ApkImportStaging.copy(root,
                () -> new ByteArrayInputStream(newBytes), () -> AVAILABLE, second[0]);
            try {
                assertArrayEquals(newBytes, Files.readAllBytes(active.candidate.toPath()));
                assertEquals(newBytes.length, active.copied.sizeBytes);
                assertTrue(second[0].isActive());
            } finally {
                active.candidate.delete();
                ImportCacheAudit.release(active.candidate);
            }
            assertOnlyOriginal(root, prior);
        } finally { deleteAll(root); }
    }

    @Test public void f122ChangedSelectionDuringProviderOpenRollsBackCandidate()
            throws Exception {
        File root = testDirectory();
        try {
            File prior = oldProject(root);
            ExportSessionGuard generations = new ExportSessionGuard();
            ExportSessionGuard.Token first = generations.begin();
            try {
                ApkImportStaging.copy(root, () -> {
                    generations.begin();
                    return new ByteArrayInputStream(new byte[]{1,2,3});
                }, () -> AVAILABLE, first);
                fail("Old provider return cannot be treated as a current import");
            } catch (InterruptedIOException expected) {
                assertFalse(first.isActive());
            }
            assertOnlyOriginal(root, prior);
        } finally { deleteAll(root); }
    }

    @Test public void f122CancelDuringWriteCannotReturnSuccessfulDigest()
            throws Exception {
        ExportSessionGuard generations = new ExportSessionGuard();
        ExportSessionGuard.Token old = generations.begin();
        ByteArrayOutputStream output = new ByteArrayOutputStream() {
            @Override public synchronized void write(byte[] bytes, int offset, int length) {
                super.write(bytes, offset, length);
                generations.begin();
            }
        };
        try {
            ApkImportPreflight.copyAndHash(
                new ByteArrayInputStream(new byte[1024]), output, () -> AVAILABLE, old);
            fail("Stale copy must fail even if the final write returned");
        } catch (InterruptedIOException expected) {
            assertEquals(1024, output.size());
        }
    }

    @Test public void f122CancelOnEofCannotApproveStaleImport()
            throws Exception {
        ExportSessionGuard generations = new ExportSessionGuard();
        ExportSessionGuard.Token old = generations.begin();
        InputStream input = new ByteArrayInputStream(new byte[256]) {
            boolean ended;
            @Override public synchronized int read(byte[] bytes, int off, int len) {
                int got = super.read(bytes, off, len);
                if (got == -1 && !ended) {
                    ended = true;
                    generations.begin();
                }
                return got;
            }
        };
        try {
            ApkImportPreflight.copyAndHash(input, new ByteArrayOutputStream(),
                () -> AVAILABLE, old);
            fail("EOF after a newer project was selected cannot be success");
        } catch (InterruptedIOException expected) {
            assertFalse(old.isActive());
        }
    }

    @Test public void f122FinalCacheAdmissionRejectsOldGeneration()
            throws Exception {
        File root = testDirectory();
        try {
            File original = oldProject(root);
            String hash = ApkIntegrity.sha256(original);
            ExportSessionGuard generations = new ExportSessionGuard();
            ExportSessionGuard.Token old = generations.begin();
            generations.begin();
            try {
                ApkCacheAdmission.verify(original, original.length(), hash, old);
                fail("Old worker may not publish a verified APK cache");
            } catch (InterruptedIOException expected) {
                assertTrue(original.exists());
            }
        } finally { deleteAll(root); }
    }

    @Test public void f122ZipAuditRejectsSupersededGeneration() throws Exception {
        File root = testDirectory();
        try {
            File zip = simpleZip(root);
            ExportSessionGuard generations = new ExportSessionGuard();
            ExportSessionGuard.Token stale = generations.begin();
            generations.begin();
            try {
                ApkZipIntegrity.verify(zip, stale);
                fail("ZIP processing must not continue for stale import");
            } catch (InterruptedIOException expected) {
                assertTrue(zip.isFile());
            }
        } finally { deleteAll(root); }
    }

    @Test public void f122IndexBuildRejectsStaleGenerationWithoutCreatingDb()
            throws Exception {
        File root = testDirectory();
        try {
            File zip = simpleZip(root);
            File index = new File(root, "candidate.idx.db");
            ExportSessionGuard generations = new ExportSessionGuard();
            ExportSessionGuard.Token old = generations.begin();
            generations.begin();
            try {
                ApkDiskIndex.build(zip, index, old);
                fail("SQLite index may not be generated for canceled import");
            } catch (InterruptedIOException expected) {
                assertFalse(index.exists());
                assertTrue(zip.isFile());
            }
        } finally { deleteAll(root); }
    }

    @Test public void f122ImportCancellationDoesNotRevokeIndependentExportSession()
            throws Exception {
        File root = testDirectory();
        try {
            File prior = oldProject(root);
            ExportSessionGuard imports = new ExportSessionGuard();
            ExportSessionGuard exports = new ExportSessionGuard();
            ExportSessionGuard.Token old = imports.begin();
            ExportSessionGuard.Token current = imports.begin();
            ExportSessionGuard.Token export = exports.begin();
            assertFalse(old.isActive());
            export.requireActive();
            ApkImportStaging.Result result = ApkImportStaging.copy(root,
                () -> new ByteArrayInputStream(new byte[]{9,8,7}),
                () -> AVAILABLE, current);
            result.candidate.delete();
            ImportCacheAudit.release(result.candidate);
            export.requireActive();
            assertOnlyOriginal(root, prior);
        } finally { deleteAll(root); }
    }
}
