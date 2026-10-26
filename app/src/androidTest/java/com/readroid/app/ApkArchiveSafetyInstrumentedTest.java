package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M2 admission tests use generated ZIP fixtures, never third-party APKs. */
@RunWith(AndroidJUnit4.class)
public final class ApkArchiveSafetyInstrumentedTest {
    private File temp() throws IOException {
        return File.createTempFile("readroid_m2_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
    }

    private static void add(ZipOutputStream zip, String name, byte[] data)
            throws IOException {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(data);
        zip.closeEntry();
    }

    private static File fixture(File file) throws IOException {
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(file))) {
            add(zip, "AndroidManifest.xml", new byte[]{3, 0, 8, 0});
            add(zip, "classes.dex", new byte[]{100, 101, 120, 10, 0, 0, 0});
            add(zip, "assets/config.txt", "Hello M2".getBytes("UTF-8"));
        }
        return file;
    }

    private static void rejected(File file) throws Exception {
        try {
            ApkArchiveSafety.verify(file);
            fail("Archive should be rejected");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    /** Locate central-directory records; keep test fixtures small/non-ZIP64. */
    private static int[] centralHeaders(byte[] bytes) {
        int[] offsets = new int[16];
        int found = 0;
        for (int i = 0; i < bytes.length - 46; i++) {
            if (bytes[i] == 0x50 && bytes[i + 1] == 0x4b
                    && bytes[i + 2] == 0x01 && bytes[i + 3] == 0x02) {
                offsets[found++] = i;
                i += 45;
            }
        }
        return Arrays.copyOf(offsets, found);
    }

    private static void uint32(byte[] bytes, int at, long value) {
        for (int j = 0; j < 4; j++) bytes[at + j] = (byte) (value >>> (j * 8));
    }

    @Test public void validDeflateAndStoredEntriesPassWithoutModifyingSource()
            throws Exception {
        File file = temp();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(file))) {
                add(zip, "AndroidManifest.xml", new byte[]{3, 0, 8, 0});
                ZipEntry stored = new ZipEntry("classes.dex");
                byte[] dex = new byte[]{100, 101, 120, 10, 0, 0, 0};
                CRC32 crc = new CRC32();
                crc.update(dex);
                stored.setMethod(ZipEntry.STORED);
                stored.setSize(dex.length);
                stored.setCompressedSize(dex.length);
                stored.setCrc(crc.getValue());
                zip.putNextEntry(stored);
                zip.write(dex);
                zip.closeEntry();
            }
            byte[] before = Files.readAllBytes(file.toPath());
            ApkArchiveSafety.Stats result = ApkArchiveSafety.verify(file);
            assertEquals(2, result.entries);
            assertEquals(2, result.files);
            assertEquals(11, result.inflatedBytes);
            assertArrayEquals(before, Files.readAllBytes(file.toPath()));
        } finally { file.delete(); }
    }

    @Test public void corruptCrcIsRejectedAndOriginalBytesStayUntouched()
            throws Exception {
        File file = temp();
        try {
            fixture(file);
            byte[] bytes = Files.readAllBytes(file.toPath());
            int[] headers = centralHeaders(bytes);
            assertEquals(3, headers.length);
            bytes[headers[2] + 16] ^= 1; // central directory CRC-32
            Files.write(file.toPath(), bytes);
            rejected(file);
            assertArrayEquals(bytes, Files.readAllBytes(file.toPath()));
        } finally { file.delete(); }
    }

    @Test public void forgedUncompressedSizeOverOneGiBIsRejected()
            throws Exception {
        File file = temp();
        try {
            fixture(file);
            byte[] bytes = Files.readAllBytes(file.toPath());
            int[] headers = centralHeaders(bytes);
            assertEquals(3, headers.length);
            uint32(bytes, headers[2] + 24, 0x40000001L);
            Files.write(file.toPath(), bytes);
            rejected(file);
        } finally { file.delete(); }
    }

    @Test public void highInflationRatioIsStoppedBeforeExtraction()
            throws Exception {
        File file = temp();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(file))) {
                add(zip, "AndroidManifest.xml", new byte[]{3, 0, 8, 0});
                zip.putNextEntry(new ZipEntry("assets/huge-zeros.bin"));
                byte[] zeros = new byte[8192];
                for (int i = 0; i < 1152; i++) zip.write(zeros); // 9 MiB
                zip.closeEntry();
            }
            assertTrue(file.length() < 64 * 1024);
            rejected(file);
        } finally { file.delete(); }
    }

    @Test public void traversalPathIsNeverAdmitted()
            throws Exception {
        File file = temp();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(file))) {
                add(zip, "../escape.txt", new byte[]{1});
            }
            rejected(file);
        } finally { file.delete(); }
    }

    @Test public void duplicateCentralDirectoryPathsAreRejected()
            throws Exception {
        File file = temp();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(file))) {
                add(zip, "assets/a.txt", new byte[]{1});
                add(zip, "assets/b.txt", new byte[]{2});
            }
            byte[] bytes = Files.readAllBytes(file.toPath());
            int[] headers = centralHeaders(bytes);
            assertEquals(2, headers.length);
            // Only change the name in the second central-directory record.
            // ZipFile may itself reject the local/central name mismatch.
            bytes[headers[1] + 46 + "assets/".length()] = (byte) 'a';
            Files.write(file.toPath(), bytes);
            rejected(file);
        } finally { file.delete(); }
    }

    @Test public void truncatedArchiveFailsWithoutCreatingAnyOutput()
            throws Exception {
        File file = temp();
        try {
            fixture(file);
            byte[] bytes = Files.readAllBytes(file.toPath());
            Files.write(file.toPath(), Arrays.copyOf(bytes, bytes.length - 12));
            rejected(file);
        } finally { file.delete(); }
    }

    @Test public void cancellationIsPromptAndDoesNotClearInterruptFlag()
            throws Exception {
        File file = temp();
        try {
            fixture(file);
            Thread.currentThread().interrupt();
            try {
                ApkArchiveSafety.verify(file);
                fail("Interrupted admission must be cancelled");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(Thread.currentThread().isInterrupted());
            } finally {
                Thread.interrupted();
            }
        } finally {
            Thread.interrupted();
            file.delete();
        }
    }
}
