package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ImportActivityScopeInstrumentedTest {
    private static final long AVAILABLE = 128L * 1024 * 1024;

    private static File folder() throws Exception {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return Files.createTempDirectory(ctx.getCacheDir().toPath(), "f125_owned_").toFile();
    }

    private static void cleanup(File directory) {
        if (directory == null) return;
        File[] children = directory.listFiles();
        if (children != null) for (File child : children) child.delete();
        directory.delete();
    }

    @Test public void f125DestroyUnlinksOnlyTrackedPrivateImport()
            throws Exception {
        File root = folder();
        try {
            File accepted = new File(root, "readroid_12345678.apk");
            Files.write(accepted.toPath(), new byte[]{1, 2, 3});
            File untracked = File.createTempFile("readroid_", ".apk", root);
            File owned = File.createTempFile("readroid_", ".apk", root);
            ImportActivityScope scope = new ImportActivityScope(root);
            scope.track(owned);
            assertEquals(1, scope.pendingCount());
            scope.close();
            assertTrue(scope.isClosed());
            assertFalse(owned.exists());
            assertTrue(accepted.exists());
            assertTrue(untracked.exists());
            assertEquals(0, scope.pendingCount());
        } finally { cleanup(root); }
    }

    @Test public void f125CommittedProjectRemainsAcrossOldActivityDestroy()
            throws Exception {
        File root = folder();
        try {
            File committed = File.createTempFile("readroid_", ".apk", root);
            Files.write(committed.toPath(), new byte[]{9, 8, 7});
            ImportActivityScope old = new ImportActivityScope(root);
            old.track(committed);
            old.release(committed);
            old.close();
            assertTrue("Previously accepted APK is not disposable", committed.isFile());
            assertArrayEquals(new byte[]{9, 8, 7}, Files.readAllBytes(committed.toPath()));
        } finally { cleanup(root); }
    }

    @Test public void f125LateRegistrationAfterDestroyCannotRecreateOldCache()
            throws Exception {
        File root = folder();
        try {
            ImportActivityScope old = new ImportActivityScope(root);
            old.close();
            File late = File.createTempFile("readroid_", ".apk", root);
            try {
                old.track(late);
                fail("Dead Activity cannot own a new candidate");
            } catch (InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("encerrada"));
            }
            assertFalse(late.exists());
            assertTrue(old.isClosed());
        } finally { cleanup(root); }
    }

    @Test public void f125ForeignAndNonImportPathsAreRejectedWithoutDeletion()
            throws Exception {
        File root = folder();
        File other = folder();
        try {
            ImportActivityScope scope = new ImportActivityScope(root);
            File outside = File.createTempFile("readroid_", ".apk", other);
            File exports = File.createTempFile("readroid_unsigned_", ".apk", root);
            File recovery = new File(root, "recovery.enc");
            Files.write(recovery.toPath(), new byte[]{1});
            for (File invalid : new File[]{outside, exports, recovery}) {
                try {
                    scope.track(invalid);
                    fail("Only a directly owned import staging file is allowed");
                } catch (IOException expected) { assertTrue(invalid.exists()); }
            }
            scope.close();
            assertTrue(outside.exists());
            assertTrue(exports.exists());
            assertTrue(recovery.exists());
        } finally {
            cleanup(root);
            cleanup(other);
        }
    }

    @Test public void f125SeparateActivityScopesDoNotDeleteEachOthersFiles()
            throws Exception {
        File root = folder();
        try {
            File stale = File.createTempFile("readroid_", ".apk", root);
            File current = File.createTempFile("readroid_", ".apk", root);
            ImportActivityScope previous = new ImportActivityScope(root);
            ImportActivityScope next = new ImportActivityScope(root);
            previous.track(stale);
            next.track(current);
            previous.close();
            assertFalse(stale.exists());
            assertTrue("Old scope may not touch new Activity staging", current.exists());
            assertFalse(next.isClosed());
            next.close();
            assertFalse(current.exists());
        } finally { cleanup(root); }
    }

    @Test public void f125SymlinkAndNestedFoldersAreNotOwnedOrRecursed()
            throws Exception {
        File root = folder();
        try {
            File target = new File(root, "user_project.apk");
            Files.write(target.toPath(), new byte[]{1});
            File symlink = new File(root, "readroid_12345678.apk");
            Files.createSymbolicLink(symlink.toPath(), target.toPath());
            File nested = new File(root, "nested");
            assertTrue(nested.mkdir());
            File child = File.createTempFile("readroid_", ".apk", nested);
            ImportActivityScope scope = new ImportActivityScope(root);
            for (File invalid : new File[]{symlink, child}) {
                try {
                    scope.track(invalid);
                    fail("Symlink or nested entry cannot be owned");
                } catch (IOException expected) {
                    assertTrue(invalid.exists());
                }
            }
            scope.close();
            assertTrue(Files.isSymbolicLink(symlink.toPath()));
            assertTrue(target.exists());
            assertTrue(child.exists());
            child.delete();
            nested.delete();
        } finally { cleanup(root); }
    }

    @Test public void f125BlockedProviderCannotRetainOldPrivateCacheAfterDestroy()
            throws Exception {
        File root = folder();
        ImportActivityScope lifetime = new ImportActivityScope(root);
        ExportSessionGuard generation = new ExportSessionGuard();
        ExportSessionGuard.Token token = generation.begin();
        CountDownLatch reading = new CountDownLatch(1);
        CountDownLatch unblock = new CountDownLatch(1);
        CountDownLatch finished = new CountDownLatch(1);
        AtomicReference<Throwable> outcome = new AtomicReference<>();
        Thread worker = new Thread(() -> {
            try {
                InputStream slow = new ByteArrayInputStream(new byte[1024]) {
                    @Override public synchronized int read(byte[] buffer, int off, int len) {
                        reading.countDown();
                        while (unblock.getCount() != 0) {
                            try { unblock.await(1, TimeUnit.SECONDS); }
                            catch (InterruptedException ignored) {
                                // Simulate a ContentProvider ignoring cancellation.
                            }
                        }
                        return super.read(buffer, off, len);
                    }
                };
                ApkImportStaging.copy(root, () -> slow, () -> AVAILABLE, token, lifetime);
            } catch (Throwable expected) {
                outcome.set(expected);
            } finally { finished.countDown(); }
        });
        try {
            worker.start();
            assertTrue(reading.await(10, TimeUnit.SECONDS));
            assertEquals(1, lifetime.pendingCount());
            File[] staged = root.listFiles();
            assertNotNull(staged);
            assertEquals(1, staged.length);
            assertTrue(staged[0].exists());
            generation.invalidate();
            lifetime.close();
            assertFalse("Dead Activity must unlink its staging immediately",
                staged[0].exists());
            unblock.countDown();
            assertTrue(finished.await(10, TimeUnit.SECONDS));
            assertTrue("Late provider return must be rejected",
                outcome.get() instanceof InterruptedIOException);
            assertEquals(0, lifetime.pendingCount());
            assertEquals(0, root.listFiles().length);
        } finally {
            generation.invalidate();
            lifetime.close();
            unblock.countDown();
            worker.join(10000);
            cleanup(root);
        }
    }

    @Test public void f125BlockedProviderOpenNeverRecreatesUnlinkedCandidate()
            throws Exception {
        File root = folder();
        ImportActivityScope lifetime = new ImportActivityScope(root);
        ExportSessionGuard generations = new ExportSessionGuard();
        ExportSessionGuard.Token token = generations.begin();
        CountDownLatch insideOpen = new CountDownLatch(1);
        CountDownLatch unblock = new CountDownLatch(1);
        CountDownLatch finished = new CountDownLatch(1);
        AtomicReference<Throwable> outcome = new AtomicReference<>();
        AtomicReference<Boolean> pathVisibleAtSourceClose = new AtomicReference<>();
        Thread worker = new Thread(() -> {
            try {
                ApkImportStaging.copy(root, () -> {
                    insideOpen.countDown();
                    while (unblock.getCount() != 0) {
                        try { unblock.await(1, TimeUnit.SECONDS); }
                        catch (InterruptedException ignored) {
                            // Simulate a DocumentsProvider that ignores interrupts.
                        }
                    }
                    return new ByteArrayInputStream(new byte[]{1, 2, 3}) {
                        @Override public void close() throws IOException {
                            File[] current = root.listFiles();
                            pathVisibleAtSourceClose.set(
                                current != null && current.length != 0);
                            super.close();
                        }
                    };
                }, () -> AVAILABLE, token, lifetime);
                outcome.set(new AssertionError("Stale SAF import was accepted"));
            } catch (Throwable result) {
                outcome.set(result);
            } finally { finished.countDown(); }
        });
        try {
            worker.start();
            assertTrue("Source.open must be blocked", insideOpen.await(10, TimeUnit.SECONDS));
            File[] files = root.listFiles();
            assertNotNull(files);
            assertEquals(1, files.length);
            assertEquals(1, lifetime.pendingCount());
            generations.invalidate();
            lifetime.close();
            assertFalse("Old temporary path must be unlinked", files[0].exists());
            unblock.countDown();
            assertTrue("Blocked worker must return", finished.await(10, TimeUnit.SECONDS));
            assertTrue("Old token must reject the late provider",
                outcome.get() instanceof InterruptedIOException);
            assertEquals("InputStream.close must not observe a recreated APK path",
                Boolean.FALSE, pathVisibleAtSourceClose.get());
            assertEquals(0, root.listFiles().length);
        } finally {
            generations.invalidate();
            lifetime.close();
            unblock.countDown();
            worker.join(10000);
            cleanup(root);
        }
    }

    @Test public void f125ClosedScopeCannotOpenStagingAgain() throws Exception {
        File root = folder();
        try {
            File candidate = File.createTempFile("readroid_", ".apk", root);
            ImportActivityScope old = new ImportActivityScope(root);
            old.track(candidate);
            old.close();
            old.close(); // idempotent, including on repeated teardown
            try {
                old.openForWrite(candidate);
                fail("Destroyed Activity cannot reacquire a writable APK path");
            } catch (InterruptedIOException expected) {
                assertTrue(old.isClosed());
            }
            assertFalse(candidate.exists());
            assertEquals(0, old.pendingCount());
        } finally { cleanup(root); }
    }
}
