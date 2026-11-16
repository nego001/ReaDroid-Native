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

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ImportCacheAuditInstrumentedTest {
    private static final long DAY = 24L * 60 * 60 * 1000;
    private static final long NOW = 1800000000000L;

    private File privateTestCache() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return Files.createTempDirectory(context.getCacheDir().toPath(),
            "f117_import_audit_").toFile();
    }

    private static File fixture(File root, String name, long ageDays) throws Exception {
        File file = new File(root, name);
        Files.write(file.toPath(), new byte[]{1, 3, 7, 9});
        assertTrue(file.setLastModified(NOW - ageDays * DAY));
        return file;
    }

    private static void cleanup(File folder) {
        File[] files = folder.listFiles();
        if (files != null) for (File file : files) {
            if (file.isDirectory() && !Files.isSymbolicLink(file.toPath()))
                cleanup(file);
            else file.delete();
        }
        folder.delete();
    }

    @Test public void healthyImportedApkAndIndexAreRecognizedWithoutMutation()
            throws Exception {
        File root = privateTestCache();
        try {
            File apk = fixture(root, "readroid_123456789.apk", 10);
            File index = fixture(root, "readroid_123456789.apk.idx.db", 10);
            byte[] before = Files.readAllBytes(apk.toPath());
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, apk, index, NOW);
            assertEquals(1, r.importedApks);
            assertEquals(1, r.sqliteIndexes);
            assertEquals(0, r.indexWithoutApk);
            assertEquals(0, r.importsWithoutIndex);
            assertEquals(2, r.activeOrRetained);
            assertEquals(0, r.oldCandidates);
            assertArrayEquals(before, Files.readAllBytes(apk.toPath()));
            assertTrue(index.exists());
        } finally { cleanup(root); }
    }

    @Test public void importWithoutIndexIsValidAndNotDeleted() throws Exception {
        File root = privateTestCache();
        try {
            File apk = fixture(root, "readroid_987654321.apk", 20);
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(1, r.importedApks);
            assertEquals(1, r.importsWithoutIndex);
            assertEquals(0, r.indexWithoutApk);
            assertTrue(apk.exists());
        } finally { cleanup(root); }
    }

    @Test public void oldIndexWithoutSourceIsOnlyReported() throws Exception {
        File root = privateTestCache();
        try {
            File index = fixture(root, "readroid_111222333.apk.idx.db", 45);
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(1, r.sqliteIndexes);
            assertEquals(1, r.indexWithoutApk);
            assertEquals(1, r.oldCandidates);
            assertTrue("No automatic deletion of recoverable index", index.exists());
        } finally { cleanup(root); }
    }

    @Test public void freshImportIsNotAnOldCandidate() throws Exception {
        File root = privateTestCache();
        try {
            File file = fixture(root, "readroid_111333444.apk", 1);
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(0, r.oldCandidates);
            assertTrue(file.exists());
        } finally { cleanup(root); }
    }

    @Test public void unsignedExportAndComparisonAreNotImports() throws Exception {
        File root = privateTestCache();
        try {
            File a = fixture(root, "readroid_unsigned_111222.apk", 45);
            File b = fixture(root, "negresco_compare_111222.apk", 45);
            File c = fixture(root, "readroid_111222.apk.tmp", 45);
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(0, r.importedApks);
            assertEquals(0, r.sqliteIndexes);
            assertEquals(0, r.oldCandidates);
            assertTrue(a.exists() && b.exists() && c.exists());
        } finally { cleanup(root); }
    }

    @Test public void symlinksAndNestedDirectoriesNeverCountOrChange()
            throws Exception {
        File root = privateTestCache();
        try {
            File target = fixture(root, "unrelated_data.bin", 45);
            Path symlink = new File(root, "readroid_12345678.apk").toPath();
            Files.createSymbolicLink(symlink, target.toPath());
            File nested = new File(root, "subfolder");
            assertTrue(nested.mkdir());
            File inside = fixture(nested, "readroid_555666777.apk", 45);
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(0, r.importedApks);
            assertTrue(Files.exists(symlink, LinkOption.NOFOLLOW_LINKS));
            assertTrue(target.exists());
            assertTrue(inside.exists());
        } finally { cleanup(root); }
    }

    @Test public void trackedActiveImportExcludedFromAgedCandidates()
            throws Exception {
        File root = privateTestCache();
        File file = null;
        try {
            file = fixture(root, "readroid_777888999.apk", 20);
            ImportCacheAudit.track(file);
            ImportCacheAudit.Report whileActive = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(1, whileActive.activeOrRetained);
            assertEquals(0, whileActive.oldCandidates);
            ImportCacheAudit.release(file);
            ImportCacheAudit.Report after = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(0, after.activeOrRetained);
            assertEquals(1, after.oldCandidates);
            assertTrue(file.exists());
        } finally {
            ImportCacheAudit.release(file);
            cleanup(root);
        }
    }

    @Test public void invalidCacheAndFutureDatedFilesAreHandledSafely() throws Exception {
        File root = privateTestCache();
        try {
            File future = fixture(root, "readroid_222333444.apk", -1);
            ImportCacheAudit.Report r = ImportCacheAudit.inspect(root, null, null, NOW);
            assertEquals(0, r.oldCandidates);
            assertEquals(1, r.importedApks);
            assertEquals(0, r.errors);
            assertTrue(future.exists());
            assertTrue(ImportCacheAudit.inspect(null, null, null, NOW).incomplete);
        } finally { cleanup(root); }
    }
}
