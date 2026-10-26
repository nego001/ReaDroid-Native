package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M2: malicious ZIPs must fail identically for JSON and SQLite explorers. */
@RunWith(AndroidJUnit4.class)
public final class ApkZipAdmissionInstrumentedTest {
    private File temp(String suffix) throws IOException {
        return File.createTempFile("negresco_m2_", suffix,
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
    }

    private static ZipEntry synthetic(String name, long size, long compressed) {
        ZipEntry entry = new ZipEntry(name);
        entry.setMethod(ZipEntry.DEFLATED);
        entry.setSize(size);
        entry.setCompressedSize(compressed);
        return entry;
    }

    private static void put(ZipOutputStream out, String path, byte[] value)
            throws IOException {
        out.putNextEntry(new ZipEntry(path));
        if (value != null) out.write(value);
        out.closeEntry();
    }

    @Test public void normalArchiveIsAdmittedByBothJsonAndSqlite() throws Exception {
        File source = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(source))) {
                put(out, "AndroidManifest.xml", new byte[]{1, 2, 3});
                put(out, "classes.dex", new byte[]{4, 5, 6});
                put(out, "assets/", null); // empty DEFLATED dir has compressed overhead
                put(out, "assets/config.json", new byte[]{'o', 'k'});
            }
            JSONObject json = ApkExplorer.inspect(source);
            ApkDiskIndex.Stats stats = ApkDiskIndex.build(source, index);
            assertEquals(3, json.getInt("fileCount"));
            assertEquals(1, json.getInt("directoryCount"));
            assertEquals(3, stats.files);
            assertEquals(1, stats.directories);
            assertEquals(8L, stats.totalUncompressedBytes);
            assertEquals(8L, json.getLong("uncompressedBytes"));
        } finally {
            source.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void oversizedExpansionIsRejectedBeforeAllocatingAnyIndex()
            throws Exception {
        File source = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            byte[] repeated = new byte[8192];
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(source))) {
                put(out, "AndroidManifest.xml", new byte[]{1});
                put(out, "classes.dex", new byte[]{2});
                out.putNextEntry(new ZipEntry("assets/mostly-zeros.bin"));
                for (int i = 0; i < 2200; i++) out.write(repeated);
                out.closeEntry();
            }
            try (ZipFile zip = new ZipFile(source)) {
                ZipEntry item = zip.getEntry("assets/mostly-zeros.bin");
                assertNotNull(item);
                assertTrue(item.getSize() > ApkZipAdmission.RATIO_CHECK_BYTES);
                assertTrue(item.getSize() / item.getCompressedSize()
                    > ApkZipAdmission.MAX_COMPRESSION_RATIO);
            }
            try {
                ApkExplorer.inspect(source);
                fail("JSON catalog admitted a high-ratio expansion");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("expansão ZIP"));
            }
            try {
                ApkDiskIndex.build(source, index);
                fail("SQLite index admitted a high-ratio expansion");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("expansão ZIP"));
                assertFalse("Failed index must be deleted", index.exists());
            }
        } finally {
            source.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void unknownSizesAndZeroCompressedLengthFailClosed()
            throws Exception {
        for (ZipEntry entry : new ZipEntry[]{
                new ZipEntry("assets/unknown.txt"),
                synthetic("assets/impossible.dat", 20L * 1024 * 1024, 0)
        }) {
            try {
                ApkZipAdmission.validateEntry(entry);
                fail("Unknown or inconsistent metadata was admitted");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("tamanho desconhecido")
                    || expected.getMessage().contains("expansão sem dados"));
            }
        }
    }

    @Test public void directoryHeadersAndLegitimateDeflateAreAccepted()
            throws Exception {
        ZipEntry directory = synthetic("assets/", 0, 2);
        ApkZipAdmission.validateEntry(directory);
        assertEquals(0, ApkZipAdmission.cumulativeBytes(0, directory));
        ApkZipAdmission.validateEntry(synthetic("assets/data.bin", 16384, 500));
        try {
            ApkZipAdmission.validateEntry(synthetic("assets/", 1, 500));
            fail("Directory with actual payload must be rejected");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Diretório"));
        }
    }

    @Test public void pathsAreConsistentlyRejectedAcrossAdmissionAndDiskIndex()
            throws Exception {
        for (String bad : new String[]{
                "../manifest.xml", "assets/../secret", "assets/./file",
                "assets//file", "/absolute", "assets\\other",
                "assets/hidden\u0000file", "assets/line\nfeed"
        }) {
            try {
                ApkZipAdmission.validatePath(bad);
                fail("ZipAdmission accepted path: " + bad);
            } catch (IOException expected) {
                // Correctly rejected.
            }
            try {
                ApkDiskIndex.validatePath(bad);
                fail("SQLite index accepted path: " + bad);
            } catch (IOException expected) {
                // Correctly rejected.
            }
        }
        ApkZipAdmission.validatePath("assets/nested/valid.xml");
        ApkDiskIndex.validatePath("assets/nested/valid.xml");
    }

    @Test public void twoGiBBudgetRejectsOverflowWithoutLongMultiplication()
            throws Exception {
        ZipEntry item = new ZipEntry("assets/stored.bin");
        item.setMethod(ZipEntry.STORED);
        item.setSize(1024L * 1024 * 1024);
        item.setCompressedSize(1024L * 1024 * 1024);
        assertEquals(ApkZipAdmission.MAX_TOTAL_BYTES,
            ApkZipAdmission.cumulativeBytes(1024L * 1024 * 1024, item));
        try {
            ApkZipAdmission.cumulativeBytes(
                1024L * 1024 * 1024 + 1, item);
            fail("Archive exceeded 2GiB declared sum");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("2 GiB"));
        }
        ZipEntry compressed = synthetic("assets/overflow.bin",
            ApkZipAdmission.MAX_ENTRY_BYTES, Long.MAX_VALUE);
        // Deliberately huge metadata must not overflow the ratio arithmetic.
        ApkZipAdmission.validateEntry(compressed);
    }
}
