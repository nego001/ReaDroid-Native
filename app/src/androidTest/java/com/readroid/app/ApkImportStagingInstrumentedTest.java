package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ApkImportStagingInstrumentedTest {
    private static final long SPACE = 128L * 1024 * 1024;

    private File folder() throws Exception {
        Context app = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return Files.createTempDirectory(app.getCacheDir().toPath(), "f121_import_").toFile();
    }

    private static File prior(File folder) throws Exception {
        File old = new File(folder, "previous_project_safe.apk");
        Files.write(old.toPath(), "unchanged prior project".getBytes(StandardCharsets.UTF_8));
        return old;
    }

    private static void verifyOnlyPriorSurvived(File folder, File prior) throws Exception {
        assertTrue(prior.isFile());
        assertArrayEquals("unchanged prior project".getBytes(StandardCharsets.UTF_8),
            Files.readAllBytes(prior.toPath()));
        File[] children = folder.listFiles();
        assertNotNull(children);
        assertEquals("Failed SAF candidate must be removed", 1, children.length);
        assertEquals(prior.getCanonicalPath(), children[0].getCanonicalPath());
    }

    private static void cleanup(File folder) {
        if (folder == null) return;
        File[] files = folder.listFiles();
        if (files != null) for (File file : files) file.delete();
        folder.delete();
    }

    @Test public void f121ProviderDeniedBeforeOpeningDeletesPrivateCandidate()
            throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            try {
                ApkImportStaging.copy(root,
                    () -> { throw new SecurityException("grant revoked"); }, () -> SPACE);
                fail("Provider revocation cannot produce imported APK");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Permissão"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121ProviderReturnsNullStreamDeletesPrivateCandidate()
            throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            try {
                ApkImportStaging.copy(root, () -> null, () -> SPACE);
                fail("Missing SAF stream cannot result in accepted project");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("não abriu"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121PartialProviderReadFailureCleansUnacceptedFile()
            throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            InputStream flaky = new ByteArrayInputStream(new byte[8192]) {
                int calls;
                @Override public synchronized int read(byte[] b, int off, int len) {
                    // Unexpected provider runtime failure: never promote partial file.
                    if (++calls > 1) throw new IllegalStateException("provider crashed");
                    return super.read(b, off, Math.min(4096, len));
                }
            };
            try {
                ApkImportStaging.copy(root, () -> flaky, () -> SPACE);
                fail("Provider failure after partial bytes cannot commit a file");
            } catch (IllegalStateException expected) {
                assertTrue(expected.getMessage().contains("crashed"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121IoErrorAfterFirstChunkDeletesCandidate() throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            InputStream source = new InputStream() {
                int reads;
                @Override public int read() throws IOException {
                    throw new IOException("transport disconnected");
                }
                @Override public int read(byte[] b, int off, int len) throws IOException {
                    if (++reads > 1) throw new IOException("transport disconnected");
                    Arrays.fill(b, off, off + Math.min(len, 1024), (byte) 3);
                    return Math.min(len, 1024);
                }
            };
            try {
                ApkImportStaging.copy(root, () -> source, () -> SPACE);
                fail("SAF IOException must roll back incomplete copy");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("disconnected"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121RevokedGrantMidReadDeletesCandidate() throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            InputStream source = new ByteArrayInputStream(new byte[1024]) {
                boolean denied;
                @Override public synchronized int read(byte[] b, int off, int len) {
                    if (denied) throw new SecurityException("permission revoked during read");
                    denied = true;
                    return super.read(b, off, Math.min(400, len));
                }
            };
            try {
                ApkImportStaging.copy(root, () -> source, () -> SPACE);
                fail("Mid-read permission revocation must roll back");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Permissão"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121StalledProviderCannotLeavePrivateCandidate() throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            InputStream stalled = new InputStream() {
                @Override public int read() { return 0; }
                @Override public int read(byte[] b, int off, int len) { return 0; }
            };
            try {
                ApkImportStaging.copy(root, () -> stalled, () -> SPACE);
                fail("Provider returning zero forever must fail and clean");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("parou de fornecer"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121CloseFailureCannotAcceptAlreadyCopiedCandidate()
            throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            InputStream source = new ByteArrayInputStream(new byte[1024]) {
                @Override public void close() throws IOException {
                    throw new IOException("provider close failed");
                }
            };
            try {
                ApkImportStaging.copy(root, () -> source, () -> SPACE);
                fail("A close error cannot promote the copied cache file");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("close failed"));
            }
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }

    @Test public void f121InterruptedWorkerDeletesPrivateCandidate()
            throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            Thread.currentThread().interrupt();
            try {
                ApkImportStaging.copy(root,
                    () -> new ByteArrayInputStream(new byte[1024]), () -> SPACE);
                fail("Interrupted import cannot create a candidate");
            } catch (java.io.InterruptedIOException expected) {
                assertNotNull(expected.getMessage());
            } finally {
                Thread.interrupted();
            }
            verifyOnlyPriorSurvived(root, old);
        } finally {
            Thread.interrupted();
            cleanup(root);
        }
    }

    @Test public void f121SuccessfulImportRetainsCandidateUntilOwnerAccepts()
            throws Exception {
        File root = folder();
        try {
            File old = prior(root);
            byte[] bytes = "Synthetic untrusted APK stream".getBytes(StandardCharsets.UTF_8);
            AtomicInteger opened = new AtomicInteger();
            ApkImportStaging.Result result = ApkImportStaging.copy(root,
                () -> {
                    opened.incrementAndGet();
                    return new ByteArrayInputStream(bytes);
                }, () -> SPACE);
            assertEquals(1, opened.get());
            assertArrayEquals(bytes, Files.readAllBytes(result.candidate.toPath()));
            assertEquals(bytes.length, result.copied.sizeBytes);
            assertEquals(2, root.listFiles().length);
            assertTrue(old.isFile());
            // Simulate MainActivity's later reject/accept handoff.
            assertTrue(result.candidate.delete());
            ImportCacheAudit.release(result.candidate);
            verifyOnlyPriorSurvived(root, old);
        } finally { cleanup(root); }
    }
}
