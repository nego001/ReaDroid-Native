package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Synthetic, non-executable ZIP/APK fixtures. No untrusted entry is extracted. */
@RunWith(AndroidJUnit4.class)
public final class ApkArchiveBudgetInstrumentedTest {
    private File temp(String suffix) throws IOException {
        return File.createTempFile("negreco_m2_", suffix,
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
    }

    private static void add(ZipOutputStream out, String name, byte[] value)
            throws IOException {
        out.putNextEntry(new ZipEntry(name));
        out.write(value);
        out.closeEntry();
    }

    @Test public void normalZipWorksInAdmissionExplorerAndSqliteIndex()
            throws Exception {
        File source = temp(".apk");
        File db = temp(".db");
        db.delete();
        try {
            try (ZipOutputStream out = new ZipOutputStream(
                    new FileOutputStream(source))) {
                add(out, "AndroidManifest.xml", new byte[]{1, 2, 3});
                add(out, "classes.dex", new byte[]{4, 5, 6});
                add(out, "assets/data.json", "{\"ok\":true}".getBytes("UTF-8"));
            }
            byte[] original = Files.readAllBytes(source.toPath());
            ApkArchiveBudget.verifyArchive(source);
            JSONObject catalog = ApkExplorer.inspect(source);
            assertEquals(3, catalog.getInt("fileCount"));
            assertEquals(17L, catalog.getLong("uncompressedBytes"));
            ApkDiskIndex.Stats index = ApkDiskIndex.build(source, db);
            assertEquals(3, index.files);
            assertEquals(17L, index.totalUncompressedBytes);
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
        } finally {
            source.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(db);
        }
    }

    @Test public void highlyCompressibleTwentyFourMiBIsRejectedWithoutExtraction()
            throws Exception {
        File source = temp(".apk");
        File db = temp(".db");
        db.delete();
        try {
            byte[] zeroes = new byte[8192];
            try (ZipOutputStream out = new ZipOutputStream(
                    new FileOutputStream(source))) {
                add(out, "AndroidManifest.xml", new byte[]{1});
                add(out, "classes.dex", new byte[]{2});
                out.putNextEntry(new ZipEntry("assets/huge-zero-padding.bin"));
                for (int i = 0; i < 3072; i++) out.write(zeroes);
                out.closeEntry();
            }
            assertTrue("Fixture must be strongly compressed",
                source.length() < 120000);
            byte[] original = Files.readAllBytes(source.toPath());
            try {
                ApkArchiveBudget.verifyArchive(source);
                fail("High-ratio archive must be blocked before analysis");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("expansão"));
            }
            try {
                ApkExplorer.inspect(source);
                fail("JSON explorer must not bypass archive policy");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("expansão"));
            }
            try {
                ApkDiskIndex.build(source, db);
                fail("SQLite index must not bypass archive policy");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("expansão"));
                assertFalse("Failing index must be rolled back", db.exists());
            }
            assertArrayEquals(original, Files.readAllBytes(source.toPath()));
        } finally {
            source.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(db);
        }
    }

    @Test public void rejectsUnknownSizesInsteadOfSilentlyTreatingAsZero()
            throws Exception {
        ApkArchiveBudget.Scan scanner = new ApkArchiveBudget.Scan();
        try {
            scanner.accept(new ZipEntry("assets/unknown.bin"));
            fail("Unknown ZIP sizes may hide expanded data");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("desconhecido"));
        }
    }

    @Test public void preventsForgedEntryAndAggregateBudgets() throws Exception {
        ApkArchiveBudget.Scan scanner = new ApkArchiveBudget.Scan();
        ZipEntry oversized = new ZipEntry("assets/large.bin");
        oversized.setSize(1024L * 1024 * 1024 + 1);
        oversized.setCompressedSize(1000000000L);
        try {
            scanner.accept(oversized);
            fail("An entry above 1 GiB is not allowed");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("1 GiB"));
        }
        ApkArchiveBudget.Scan total = new ApkArchiveBudget.Scan();
        for (int i = 0; i < 2; i++) {
            ZipEntry piece = new ZipEntry("assets/part" + i + ".bin");
            piece.setSize(1024L * 1024 * 1024);
            piece.setCompressedSize(1024L * 1024 * 1024);
            total.accept(piece);
        }
        ZipEntry overflow = new ZipEntry("assets/third.bin");
        overflow.setSize(1);
        overflow.setCompressedSize(1);
        try {
            total.accept(overflow);
            fail("Aggregated expanded bytes exceed 2 GiB");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("2 GiB"));
        }
    }

    @Test public void rejectsDuplicateTraversalAndNulPaths() throws Exception {
        ApkArchiveBudget.Scan scan = new ApkArchiveBudget.Scan();
        ZipEntry valid = new ZipEntry("assets/ok.json");
        valid.setSize(4);
        valid.setCompressedSize(4);
        scan.accept(valid);
        try {
            scan.accept(valid);
            fail("Duplicate path not allowed");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("duplicada"));
        }
        for (String unsafe : new String[]{
                "../escape.bin", "assets/../escape.bin", "assets//bad.bin",
                "assets/./bad.bin", "/root.bin", "assets\\evil", "assets/\u0000hidden"}) {
            ZipEntry bad = new ZipEntry(unsafe);
            bad.setSize(3);
            bad.setCompressedSize(3);
            try {
                new ApkArchiveBudget.Scan().accept(bad);
                fail("Unsafe archive path was accepted: " + unsafe);
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("insegur"));
            }
        }
    }

    @Test public void cancellationStopsAdmissionBeforeScanningMoreEntries()
            throws Exception {
        Thread.currentThread().interrupt();
        try {
            new ApkArchiveBudget.Scan().accept(new ZipEntry("assets/valid.txt"));
            fail("Interrupted inspection must stop");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(expected.getMessage().contains("cancelada"));
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void brokenZipIsRejectedWithoutModifyingSource() throws Exception {
        File source = temp(".apk");
        try {
            byte[] invalid = new byte[]{80, 75, 3, 4, 0, 0};
            Files.write(source.toPath(), invalid);
            try {
                ApkArchiveBudget.verifyArchive(source);
                fail("Corrupt central directory cannot be admitted");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
            assertTrue(Arrays.equals(invalid, Files.readAllBytes(source.toPath())));
        } finally {
            source.delete();
        }
    }

    @Test public void ratioThresholdDoesNotRejectSmallTextMetadata()
            throws Exception {
        ZipEntry small = new ZipEntry("assets/small.txt");
        small.setSize(1024L * 1024);
        small.setCompressedSize(1000);
        ApkArchiveBudget.Scan scanner = new ApkArchiveBudget.Scan();
        scanner.accept(small);
        assertEquals(1024L * 1024, scanner.uncompressedBytes());
    }
}
