package com.readroid.app;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.*;

/**
 * Uses actual Android ContentResolver and separately registered AndroidTest
 * provider, not Java fake source streams. The provider has NO production
 * manifest declaration and cannot modify the user's original SAF documents.
 */
@RunWith(AndroidJUnit4.class)
public final class F129RealProviderInstrumentedTest {
    private static final long SPACE = 128L * 1024 * 1024;

    private static Context target() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }
    private static ContentResolver resolver() { return target().getContentResolver(); }

    private static void command(String method) {
        Bundle status = resolver().call(F129FaultyContentProvider.AUTHORITY,
            method, null, null);
        assertNotNull("Test provider unavailable: " + method, status);
        assertTrue("Test provider refused " + method, status.getBoolean("ok"));
    }

    private static File folder() throws Exception {
        return Files.createTempDirectory(target().getCacheDir().toPath(),
            "f129_provider_").toFile();
    }

    private static File[] protectedFiles(File root) throws Exception {
        File apk = new File(root, "readroid_F129accepted123.apk");
        File index = new File(root, "readroid_F129accepted123.apk.idx.db");
        File recovery = new File(root, "recovery_f129.enc");
        Files.write(apk.toPath(), "accepted-project".getBytes(StandardCharsets.UTF_8));
        Files.write(index.toPath(), "sqlite-index".getBytes(StandardCharsets.UTF_8));
        Files.write(recovery.toPath(), "recovery-checkpoint".getBytes(StandardCharsets.UTF_8));
        return new File[]{apk, index, recovery};
    }

    private static void assertNoCandidate(File root, File[] originals)
            throws Exception {
        assertEquals("Unexpected orphan APK or SAF pending cache",
            originals.length, root.listFiles().length);
        String[] expected = {"accepted-project", "sqlite-index", "recovery-checkpoint"};
        for (int i = 0; i < originals.length; i++) {
            assertTrue(originals[i].isFile());
            assertEquals(expected[i], new String(
                Files.readAllBytes(originals[i].toPath()), StandardCharsets.UTF_8));
        }
    }

    private static void cleanup(File root) {
        if (root == null) return;
        File[] children = root.listFiles();
        if (children != null) for (File child : children) child.delete();
        root.delete();
    }

    @Test public void f129MetadataVisibleButDocumentGoneBeforeOpenCannotImport()
            throws Exception {
        File root = folder();
        ImportActivityScope scope = new ImportActivityScope(root);
        try {
            File[] existing = protectedFiles(root);
            ApkImportPreflight.beforeCopy(target(), F129FaultyContentProvider.MISSING);
            try {
                ApkImportStaging.copy(root, () -> resolver().openInputStream(
                    F129FaultyContentProvider.MISSING), () -> SPACE, null, scope);
                fail("Missing document cannot complete SAF import");
            } catch (FileNotFoundException expected) {
                assertNotNull(expected.getMessage());
            }
            assertNoCandidate(root, existing);
        } finally { scope.close(); cleanup(root); }
    }

    @Test public void f129TruncatedProviderPipeIsNeverAcceptedAsApk()
            throws Exception {
        File root = folder();
        ImportActivityScope scope = new ImportActivityScope(root);
        try {
            File[] existing = protectedFiles(root);
            command("arm");
            ApkImportPreflight.beforeCopy(target(), F129FaultyContentProvider.TRUNCATED);
            File promoted = null;
            try {
                ApkImportStaging.Result result = ApkImportStaging.copy(root,
                    () -> resolver().openInputStream(F129FaultyContentProvider.TRUNCATED),
                    () -> SPACE, null, scope);
                promoted = result.candidate;
                assertTrue("Only completely streamed staging may be promoted",
                    promoted.getName().endsWith(".apk"));
                try {
                    ApkZipIntegrity.verify(promoted);
                    fail("Short untrusted pipe must fail ZIP/CRC validation");
                } catch (IOException expected) {
                    // ZIP never reaches MainActivity commit; no new project.
                }
            } catch (IOException transportAborted) {
                // Broken provider pipes can report EIO instead of clean EOF.
                // In either case, nothing is accepted as a project.
            } finally {
                if (promoted != null) {
                    promoted.delete();
                    ImportCacheAudit.release(promoted);
                    scope.release(promoted);
                }
            }
            assertNoCandidate(root, existing);
        } finally { scope.close(); cleanup(root); }
    }

    @Test public void f129ProviderRevokedWhileBlockedCannotResurrectOldActivity()
            throws Exception {
        File root = folder();
        ImportActivityScope scope = new ImportActivityScope(root);
        ExportSessionGuard generations = new ExportSessionGuard();
        ExportSessionGuard.Token old = generations.begin();
        CountDownLatch finished = new CountDownLatch(1);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread worker = null;
        try {
            File[] existing = protectedFiles(root);
            command("arm");
            worker = new Thread(() -> {
                try {
                    ApkImportStaging.copy(root, () -> resolver().openInputStream(
                        F129FaultyContentProvider.BLOCKED), () -> SPACE, old, scope);
                    failure.set(new AssertionError("Stale provider was accepted"));
                } catch (Throwable outcome) { failure.set(outcome); }
                finally { finished.countDown(); }
            }, "F129-import-worker");
            worker.start();
            command("await-first");
            assertEquals(1, scope.pendingCount());
            File[] before = root.listFiles();
            assertEquals(existing.length + 1, before.length);
            File uncommitted = null;
            for (File f : before)
                if (f.getName().endsWith(".apk.pending")) uncommitted = f;
            assertNotNull("Partial file was not staged before revocation", uncommitted);
            generations.invalidate();
            scope.close();
            assertFalse("Old Activity must unlink blocked import",
                uncommitted.exists());
            // Provider can deny future opens and release a previously opened FD;
            // no already-open FD is assumed revoked by the Android framework.
            command("revoke");
            command("release");
            assertTrue("Blocked SAF worker failed to settle",
                finished.await(12, TimeUnit.SECONDS));
            assertTrue("Generation guard must reject stale ContentResolver read",
                failure.get() instanceof InterruptedIOException);
            try {
                resolver().openInputStream(F129FaultyContentProvider.BLOCKED);
                fail("Revoked provider must refuse subsequent open");
            } catch (FileNotFoundException expected) {
                // Provider-level revocation, not platform persisted grant.
            }
            assertNoCandidate(root, existing);
        } finally {
            generations.invalidate();
            scope.close();
            try { command("release"); } catch (Exception ignored) {}
            if (worker != null) worker.join(12000);
            cleanup(root);
        }
    }
}
