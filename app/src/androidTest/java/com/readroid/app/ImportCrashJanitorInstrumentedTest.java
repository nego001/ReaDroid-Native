package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.LinkOption;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ImportCrashJanitorInstrumentedTest {
    private static File folder() throws Exception {
        Context app = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return Files.createTempDirectory(app.getCacheDir().toPath(),
            "f126_crash_").toFile();
    }

    private static void cleanup(File root) {
        if (root == null) return;
        File[] entries = root.listFiles();
        if (entries != null) for (File file : entries) {
            if (file.isDirectory() && !Files.isSymbolicLink(file.toPath()))
                cleanup(file);
            else file.delete();
        }
        root.delete();
    }

    @Test public void f126SimulatedProcessDeathDeletesOnlyIncompleteSafCopy()
            throws Exception {
        File root = folder();
        try {
            // A killed process never runs ImportActivityScope.close().
            File abandoned = File.createTempFile("readroid_", ".apk.pending", root);
            Files.write(abandoned.toPath(), new byte[]{1, 2, 3});
            File accepted = new File(root, "readroid_123456789.apk");
            File sqlite = new File(root, "readroid_123456789.apk.idx.db");
            File recovery = new File(root, "recovery.enc");
            Files.write(accepted.toPath(), new byte[]{7, 8, 9});
            Files.write(sqlite.toPath(), new byte[]{1, 4});
            Files.write(recovery.toPath(), new byte[]{5});
            ImportCrashJanitor.Report result = ImportCrashJanitor.sweep(root);
            assertEquals(1, result.deleted);
            assertEquals(0, result.errors);
            assertFalse(result.incomplete);
            assertFalse(abandoned.exists());
            assertArrayEquals(new byte[]{7, 8, 9}, Files.readAllBytes(accepted.toPath()));
            assertArrayEquals(new byte[]{1, 4}, Files.readAllBytes(sqlite.toPath()));
            assertTrue(recovery.isFile());
            assertEquals(0, ImportCrashJanitor.sweep(root).deleted);
        } finally { cleanup(root); }
    }

    @Test public void f126SymlinksNestedAndUnrelatedNamesAreNeverDeleted()
            throws Exception {
        File root = folder();
        File outside = folder();
        try {
            File target = new File(outside, "preserve.bin");
            Files.write(target.toPath(), new byte[]{1, 2, 3});
            Path link = new File(root, "readroid_12345678.apk.pending").toPath();
            Files.createSymbolicLink(link, target.toPath());
            File nested = new File(root, "nested");
            assertTrue(nested.mkdir());
            File inside = File.createTempFile("readroid_", ".apk.pending", nested);
            File export = new File(root, "readroid_unsigned_123456.apk.pending");
            File malformed = new File(root, "readroid_12.apk.pending");
            Files.write(export.toPath(), new byte[]{2});
            Files.write(malformed.toPath(), new byte[]{3});
            ImportCrashJanitor.Report result = ImportCrashJanitor.sweep(root);
            assertEquals(0, result.deleted);
            assertTrue(Files.isSymbolicLink(link));
            assertTrue(target.isFile());
            assertTrue(inside.isFile());
            assertTrue(export.isFile());
            assertTrue(malformed.isFile());
        } finally { cleanup(root); cleanup(outside); }
    }

    @Test public void f126SuccessfulCopyIsAtomicallyNamedAndSafeAtNextStartup()
            throws Exception {
        File root = folder();
        try {
            ImportActivityScope scope = new ImportActivityScope(root);
            ExportSessionGuard session = new ExportSessionGuard();
            byte[] bytes = new byte[]{1, 2, 3, 4};
            ApkImportStaging.Result copied = ApkImportStaging.copy(root,
                () -> new ByteArrayInputStream(bytes),
                () -> 128L * 1024 * 1024, session.begin(), scope);
            assertTrue(copied.candidate.getName().endsWith(".apk"));
            assertFalse(copied.candidate.getName().endsWith(".pending"));
            assertArrayEquals(bytes, Files.readAllBytes(copied.candidate.toPath()));
            assertEquals(0, ImportCrashJanitor.sweep(root).deleted);
            assertTrue("Complete APK must not be removed on startup",
                copied.candidate.isFile());
            // Full-copy does not equal acceptance into MainActivity.
            scope.close();
            assertFalse("Unaccepted candidate is still owned by old Activity",
                copied.candidate.exists());
        } finally { cleanup(root); }
    }

    @Test public void f126InvalidRootFailsClosed() {
        assertTrue(ImportCrashJanitor.sweep(null).incomplete);
        assertFalse(ImportCrashJanitor.pendingName("readroid_12345678.apk"));
        assertFalse(ImportCrashJanitor.pendingName("readroid_unsigned_123456.apk.pending"));
        assertFalse(ImportCrashJanitor.pendingName("readroid_12.apk.pending"));
        assertTrue(ImportCrashJanitor.pendingName("readroid_12345678.apk.pending"));
    }
}
