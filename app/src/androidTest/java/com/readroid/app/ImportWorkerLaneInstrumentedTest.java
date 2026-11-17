package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ImportWorkerLaneInstrumentedTest {
    private static final long AVAILABLE = 128L * 1024 * 1024;

    private static boolean reached(CountDownLatch latch) throws InterruptedException {
        return latch.await(10, TimeUnit.SECONDS);
    }

    @Test public void f124ImmediateAdmissionDoesNotReportQueueWait() throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch completed = new CountDownLatch(1);
        try {
            ImportWorkerLane.Submission admission = lane.submit(completed::countDown);
            assertFalse("First available SAF worker must not look queued",
                admission.waiting);
            assertTrue(reached(completed));
        } finally { lane.shutdownNow(); }
    }

    @Test public void f124SaturatedAdmissionWaitsUntilProviderReleases() throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch busy = new CountDownLatch(2);
        CountDownLatch free = new CountDownLatch(1);
        CountDownLatch newestStarted = new CountDownLatch(1);
        try {
            Runnable blocker = () -> {
                busy.countDown();
                try { free.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
            };
            lane.execute(blocker);
            lane.execute(blocker);
            assertTrue(reached(busy));
            ImportWorkerLane.Submission admission = lane.submit(newestStarted::countDown);
            assertTrue("Newest selection must show waiting when both SAF readers block",
                admission.waiting);
            assertEquals(2, admission.activeWorkers);
            assertEquals(1, lane.pendingCount());
            assertEquals(1L, newestStarted.getCount());
            free.countDown();
            assertTrue("Queued import must resume when reader is released",
                reached(newestStarted));
        } finally {
            free.countDown();
            lane.shutdownNow();
        }
    }

    @Test public void f124WaitingNoticeBelongsOnlyToNewestQueuedSelection()
            throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch busy = new CountDownLatch(2);
        CountDownLatch free = new CountDownLatch(1);
        CountDownLatch newestStarted = new CountDownLatch(1);
        AtomicInteger supersededStarted = new AtomicInteger();
        ExportSessionGuard sessions = new ExportSessionGuard();
        try {
            Runnable blocker = () -> {
                busy.countDown();
                try { free.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
            };
            lane.execute(blocker);
            lane.execute(blocker);
            assertTrue(reached(busy));
            ExportSessionGuard.Token old = sessions.begin();
            ImportWorkerLane.Submission first = lane.submit(() -> {
                supersededStarted.incrementAndGet();
                assertFalse("Superseded import must not be live", old.isActive());
            });
            assertTrue(first.waiting);
            ExportSessionGuard.Token current = sessions.begin();
            ImportWorkerLane.Submission newest = lane.submit(() -> {
                assertTrue(current.isActive());
                newestStarted.countDown();
            });
            assertTrue(newest.waiting);
            assertEquals(1, lane.pendingCount());
            free.countDown();
            assertTrue(reached(newestStarted));
            assertEquals("Evicted queued import must never start",
                0, supersededStarted.get());
        } finally {
            free.countDown();
            lane.shutdownNow();
        }
    }

    @Test public void f124ShutdownDoesNotResumePreviouslyQueuedSelection()
            throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch busy = new CountDownLatch(2);
        CountDownLatch free = new CountDownLatch(1);
        AtomicBoolean startedAfterShutdown = new AtomicBoolean(false);
        try {
            Runnable blocker = () -> {
                busy.countDown();
                try { free.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); }
            };
            lane.execute(blocker);
            lane.execute(blocker);
            assertTrue(reached(busy));
            assertTrue(lane.submit(() -> startedAfterShutdown.set(true)).waiting);
            lane.shutdownNow();
            free.countDown();
            assertFalse(startedAfterShutdown.get());
            assertTrue(lane.isShutdown());
        } finally {
            free.countDown();
            lane.shutdownNow();
        }
    }

    @Test public void f123BlockedSafReadDoesNotBlockSecondImportOrOtherWork()
            throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        ExecutorService otherTasks = Executors.newSingleThreadExecutor();
        ExportSessionGuard sessions = new ExportSessionGuard();
        File root = Files.createTempDirectory(
            InstrumentationRegistry.getInstrumentation()
                .getTargetContext().getCacheDir().toPath(), "f123_blocked_").toFile();
        CountDownLatch blocked = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        CountDownLatch oldDone = new CountDownLatch(1);
        CountDownLatch latestDone = new CountDownLatch(1);
        CountDownLatch otherDone = new CountDownLatch(1);
        AtomicBoolean oldCancelled = new AtomicBoolean(false);
        try {
            ExportSessionGuard.Token old = sessions.begin();
            lane.execute(() -> {
                try {
                    InputStream provider = new ByteArrayInputStream(new byte[64]) {
                        boolean waiting;
                        @Override public synchronized int read(byte[] b, int off, int len) {
                            if (!waiting) {
                                waiting = true;
                                blocked.countDown();
                                try { release.await(10, TimeUnit.SECONDS); }
                                catch (InterruptedException stop) {
                                    Thread.currentThread().interrupt();
                                }
                            }
                            return super.read(b, off, len);
                        }
                    };
                    ApkImportStaging.copy(root, () -> provider, () -> AVAILABLE, old);
                } catch (InterruptedIOException cancelled) {
                    oldCancelled.set(true);
                } catch (Exception error) {
                    throw new AssertionError(error);
                } finally {
                    oldDone.countDown();
                }
            });
            assertTrue("First provider never started", reached(blocked));
            ExportSessionGuard.Token latest = sessions.begin();
            lane.execute(() -> {
                try {
                    ApkImportStaging.Result result = ApkImportStaging.copy(root,
                        () -> new ByteArrayInputStream(new byte[]{1,2,3}),
                        () -> AVAILABLE, latest);
                    result.candidate.delete();
                    ImportCacheAudit.release(result.candidate);
                } catch (Exception e) {
                    throw new AssertionError(e);
                } finally { latestDone.countDown(); }
            });
            otherTasks.execute(otherDone::countDown);
            assertTrue("New import waited behind a blocked provider", reached(latestDone));
            assertTrue("Export/recovery lane blocked behind SAF", reached(otherDone));
            assertEquals("First provider must still own one blocked worker",
                1L, oldDone.getCount());
            release.countDown();
            assertTrue(reached(oldDone));
            assertTrue(oldCancelled.get());
        } finally {
            release.countDown();
            lane.shutdownNow();
            otherTasks.shutdownNow();
            File[] files = root.listFiles();
            if (files != null) for (File file : files) file.delete();
            root.delete();
        }
    }

    @Test public void f123OnlyLatestOfManyQueuedImportsCanExecute()
            throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch started = new CountDownLatch(2);
        CountDownLatch release = new CountDownLatch(1);
        CountDownLatch latestExecuted = new CountDownLatch(1);
        AtomicInteger outdatedExecuted = new AtomicInteger();
        try {
            Runnable blocker = () -> {
                started.countDown();
                try { release.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException stop) { Thread.currentThread().interrupt(); }
            };
            lane.execute(blocker);
            lane.execute(blocker);
            assertTrue(reached(started));
            for (int i=0; i<32; i++) {
                lane.execute(i==31 ? latestExecuted::countDown
                    : outdatedExecuted::incrementAndGet);
                assertTrue("Pending SAF requests must be bounded",
                    lane.pendingCount() <= ImportWorkerLane.MAX_PENDING);
                assertTrue(lane.activeCount() <= ImportWorkerLane.MAX_RUNNING);
            }
            assertEquals(1, lane.pendingCount());
            release.countDown();
            assertTrue(reached(latestExecuted));
            assertEquals("Evicted pending imports must not execute",
                0, outdatedExecuted.get());
        } finally {
            release.countDown();
            lane.shutdownNow();
        }
    }

    @Test public void f123ShutdownRejectsImportAndDropsQueuedWork()
            throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch started = new CountDownLatch(2);
        CountDownLatch release = new CountDownLatch(1);
        AtomicBoolean queued = new AtomicBoolean(false);
        try {
            Runnable blocker = () -> {
                started.countDown();
                try { release.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException stop) { Thread.currentThread().interrupt(); }
            };
            lane.execute(blocker);
            lane.execute(blocker);
            assertTrue(reached(started));
            lane.execute(() -> queued.set(true));
            lane.shutdownNow();
            release.countDown();
            assertTrue(lane.isShutdown());
            assertFalse(queued.get());
            try {
                lane.execute(() -> queued.set(true));
                fail("Destroyed Activity may not start another import");
            } catch (RejectedExecutionException expected) {
                assertFalse(queued.get());
            }
        } finally {
            release.countDown();
            lane.shutdownNow();
        }
    }

    @Test public void f123IndependentLaneCanRunWhileSharedExecutorIsBusy()
            throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        ExecutorService other = Executors.newSingleThreadExecutor();
        CountDownLatch started = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        CountDownLatch importDone = new CountDownLatch(1);
        try {
            other.execute(() -> {
                started.countDown();
                try { release.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException stop) { Thread.currentThread().interrupt(); }
            });
            assertTrue(reached(started));
            lane.execute(importDone::countDown);
            assertTrue("Import must not depend on shared executor", reached(importDone));
        } finally {
            release.countDown();
            lane.shutdownNow();
            other.shutdownNow();
        }
    }

    @Test public void f123NoMoreThanTwoConcurrentImports() throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        CountDownLatch started = new CountDownLatch(2);
        CountDownLatch release = new CountDownLatch(1);
        try {
            Runnable blocker = () -> {
                started.countDown();
                try { release.await(10, TimeUnit.SECONDS); }
                catch (InterruptedException stop) { Thread.currentThread().interrupt(); }
            };
            lane.execute(blocker);
            lane.execute(blocker);
            assertTrue(reached(started));
            assertEquals(2, lane.activeCount());
            lane.execute(() -> {});
            assertEquals(1, lane.pendingCount());
        } finally {
            release.countDown();
            lane.shutdownNow();
        }
    }

    @Test public void f123CompletedImportLaneRemainsReusable() throws Exception {
        ImportWorkerLane lane = new ImportWorkerLane();
        try {
            for (int i=0;i<4;i++) {
                CountDownLatch done = new CountDownLatch(1);
                lane.execute(done::countDown);
                assertTrue(reached(done));
            }
            assertFalse(lane.isShutdown());
        } finally { lane.shutdownNow(); }
    }
}
