package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.*;

/**
 * F1.16: all cleanup tests run within a dedicated private test directory.
 * Production only sweeps the app's cache root; no real user project is touched.
 */
@RunWith(AndroidJUnit4.class)
public final class RebuildTempJanitorInstrumentedTest {
    private static final long DAY = RebuildTempJanitor.MIN_STALE_AGE_MS;
    private static final long NOW = 1800000000000L;

    private File root() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return Files.createTempDirectory(context.getCacheDir().toPath(),
            "f116_janitor_test_").toFile();
    }

    private static File entry(File root, String prefix, String suffix, long modified)
            throws Exception {
        File f = File.createTempFile(prefix, suffix, root);
        assertTrue("Failed to set fixture modification time", f.setLastModified(modified));
        return f;
    }

    private static void cleanup(File root) {
        if (root == null || !root.exists()) return;
        File[] items = root.listFiles();
        if (items != null) for (File item : items) {
            if (item.isDirectory() && !Files.isSymbolicLink(item.toPath()))
                cleanup(item);
            else item.delete();
        }
        root.delete();
    }

    @Test public void oldUnsignedAndZipStagingFilesArePruned() throws Exception {
        File root = root();
        try {
            File unsigned = entry(root, "readroid_unsigned_", ".apk", NOW - DAY - 5);
            File staging = entry(root, "readroid-rebuild-", ".tmp", NOW - DAY - 5);
            RebuildTempJanitor.Result result = RebuildTempJanitor.sweep(root, NOW, DAY);
            assertEquals(2, result.deleted);
            assertEquals(0, result.failed);
            assertFalse(unsigned.exists());
            assertFalse(staging.exists());
        } finally { cleanup(root); }
    }

    @Test public void freshOrFutureDatedFilesAreNeverRemoved() throws Exception {
        File root = root();
        try {
            File fresh = entry(root, "readroid_unsigned_", ".apk", NOW - DAY + 1);
            File future = entry(root, "readroid-rebuild-", ".tmp", NOW + 1000);
            RebuildTempJanitor.Result result = RebuildTempJanitor.sweep(root, NOW, DAY);
            assertEquals(0, result.deleted);
            assertTrue(fresh.exists());
            assertTrue(future.exists());
        } finally { cleanup(root); }
    }

    @Test public void importedApksRecoveryAndUnrelatedCacheRemainUntouched()
            throws Exception {
        File root = root();
        try {
            File imported = entry(root, "readroid_", ".apk", NOW - DAY - 50);
            File comparison = entry(root, "negresco_compare_", ".apk", NOW - DAY - 50);
            File recovery = entry(root, "readroid_recovery_", ".bin", NOW - DAY - 50);
            File misleading = entry(root, "readroid_unsigned_", ".txt", NOW - DAY - 50);
            RebuildTempJanitor.Result result = RebuildTempJanitor.sweep(root, NOW, DAY);
            assertEquals(0, result.deleted);
            assertTrue(imported.exists());
            assertTrue(comparison.exists());
            assertTrue(recovery.exists());
            assertTrue(misleading.exists());
        } finally { cleanup(root); }
    }

    @Test public void activeOldExportIsProtectedUntilReleased() throws Exception {
        File root = root();
        File working = null;
        try {
            working = entry(root, "readroid_unsigned_", ".apk", NOW - DAY - 30);
            RebuildTempJanitor.track(working);
            assertEquals(0, RebuildTempJanitor.sweep(root, NOW, DAY).deleted);
            assertTrue(working.exists());
            RebuildTempJanitor.release(working);
            assertEquals(1, RebuildTempJanitor.sweep(root, NOW, DAY).deleted);
            assertFalse(working.exists());
        } finally {
            RebuildTempJanitor.release(working);
            cleanup(root);
        }
    }

    @Test public void childDirectoryIsNotRecursivelyCleaned() throws Exception {
        File root = root();
        try {
            File subdir = new File(root, "readroid_unsigned_123456.apk");
            assertTrue(subdir.mkdir());
            File nested = entry(subdir, "readroid-rebuild-", ".tmp", NOW - DAY - 50);
            assertEquals(0, RebuildTempJanitor.sweep(root, NOW, DAY).deleted);
            assertTrue(subdir.isDirectory());
            assertTrue(nested.exists());
        } finally { cleanup(root); }
    }

    @Test public void symlinkIsNotFollowedOrDeleted() throws Exception {
        File root = root();
        try {
            File target = entry(root, "readroid_", ".apk", NOW - DAY - 50);
            Path link = new File(root, "readroid_unsigned_123456.apk").toPath();
            Files.createSymbolicLink(link, target.toPath());
            assertTrue(Files.isSymbolicLink(link));
            assertEquals(0, RebuildTempJanitor.sweep(root, NOW, DAY).deleted);
            assertTrue(Files.exists(link, LinkOption.NOFOLLOW_LINKS));
            assertTrue(target.exists());
        } finally { cleanup(root); }
    }

    @Test public void processingIsBoundedForLargeCandidateSets() throws Exception {
        File root = root();
        try {
            List<File> old = new ArrayList<>();
            for (int i = 0; i < RebuildTempJanitor.MAX_DELETED + 5; i++)
                old.add(entry(root, "readroid-rebuild-", ".tmp", NOW - DAY - 99));
            RebuildTempJanitor.Result result = RebuildTempJanitor.sweep(root, NOW, DAY);
            assertEquals(RebuildTempJanitor.MAX_DELETED, result.deleted);
            int surviving = 0;
            for (File f : old) if (f.exists()) surviving++;
            assertEquals(5, surviving);
        } finally { cleanup(root); }
    }

    @Test public void tooShortAgeOrInvalidRootCannotPrune() throws Exception {
        File root = root();
        try {
            File old = entry(root, "readroid_unsigned_", ".apk", NOW - DAY - 5);
            assertEquals(0, RebuildTempJanitor.sweep(root, NOW, 0).deleted);
            assertEquals(0, RebuildTempJanitor.sweep(null, NOW, DAY).deleted);
            assertTrue(old.exists());
        } finally { cleanup(root); }
    }
}
