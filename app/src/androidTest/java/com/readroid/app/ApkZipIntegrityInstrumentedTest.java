package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Synthetic ZIP fixtures; never touches a user APK or a release artifact. */
@RunWith(AndroidJUnit4.class)
public final class ApkZipIntegrityInstrumentedTest {
    private File fixture() throws IOException {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return File.createTempFile("f16_zip_", ".apk", ctx.getCacheDir());
    }

    private static byte[] bytes(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }

    private static void add(ZipOutputStream out, String name, byte[] data,
                            boolean stored) throws IOException {
        ZipEntry e = new ZipEntry(name);
        if (stored) {
            CRC32 crc = new CRC32();
            crc.update(data);
            e.setMethod(ZipEntry.STORED);
            e.setSize(data.length);
            e.setCompressedSize(data.length);
            e.setCrc(crc.getValue());
        }
        out.putNextEntry(e);
        out.write(data);
        out.closeEntry();
    }

    private static void writeFixture(File file, boolean stored) throws IOException {
        try (ZipOutputStream out = new ZipOutputStream(Files.newOutputStream(file.toPath()))) {
            add(out, "assets/", new byte[0], true);
            add(out, "assets/config.txt", bytes("F16_STORED_UNIQUE_MARKER"), stored);
            add(out, "classes.dex", bytes("F16 deflated bytes 12345"), false);
            add(out, "assets/empty.bin", new byte[0], false);
        }
    }

    private static int locate(byte[] src, byte[] target) {
        outer: for (int i = 0; i <= src.length - target.length; i++) {
            for (int j = 0; j < target.length; j++) {
                if (src[i + j] != target[j]) continue outer;
            }
            return i;
        }
        return -1;
    }

    private static int centralEntry(byte[] zip, String entryName) {
        byte[] name = bytes(entryName);
        // Match name immediately following a central-directory record.
        // The first central record may be a zero-byte directory.
        for (int i = 46; i <= zip.length - name.length; i++) {
            int header = i - 46;
            if ((zip[header] & 255) != 0x50
                    || (zip[header + 1] & 255) != 0x4b
                    || (zip[header + 2] & 255) != 0x01
                    || (zip[header + 3] & 255) != 0x02)
                continue;
            int nameLength = (zip[header + 28] & 255)
                    | ((zip[header + 29] & 255) << 8);
            if (nameLength != name.length) continue;
            boolean same = true;
            for (int j = 0; j < name.length; j++) {
                if (zip[i + j] != name[j]) { same = false; break; }
            }
            if (same) return header;
        }
        return -1;
    }

    private static void assertCorrupt(File file) throws Exception {
        try {
            ApkZipIntegrity.verify(file);
            fail("A damaged member must not pass ZIP audit");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void readsAllDeflatedStoredAndEmptyFiles() throws Exception {
        File file = fixture();
        try {
            writeFixture(file, true);
            ApkZipIntegrity.Result result = ApkZipIntegrity.verify(file);
            assertEquals(3, result.verifiedFiles);
            assertEquals(bytes("F16_STORED_UNIQUE_MARKER").length
                    + bytes("F16 deflated bytes 12345").length, result.uncompressedBytes);
        } finally { file.delete(); }
    }

    @Test public void storedPayloadChangedWithoutNewCrcIsRejected() throws Exception {
        File file = fixture();
        try {
            writeFixture(file, true);
            byte[] zip = Files.readAllBytes(file.toPath());
            int position = locate(zip, bytes("F16_STORED_UNIQUE_MARKER"));
            assertTrue(position >= 0);
            zip[position + 3] ^= 1;
            Files.write(file.toPath(), zip);
            assertCorrupt(file);
        } finally { file.delete(); }
    }

    @Test public void deflatedPayloadWithForgedCentralCrcIsRejected() throws Exception {
        File file = fixture();
        try {
            writeFixture(file, false);
            byte[] zip = Files.readAllBytes(file.toPath());
            int central = centralEntry(zip, "assets/config.txt");
            assertTrue(central >= 0);
            // Central directory CRC32 is at +16; leaving compressed bytes
            // untouched proves that simply reading the entry is insufficient.
            for (int i = 0; i < 4; i++) zip[central + 16 + i] = 0;
            Files.write(file.toPath(), zip);
            assertCorrupt(file);
        } finally { file.delete(); }
    }

    @Test public void advertisedSizeTooSmallCannotHideInflation() throws Exception {
        File file = fixture();
        try {
            writeFixture(file, false);
            byte[] zip = Files.readAllBytes(file.toPath());
            int central = centralEntry(zip, "assets/config.txt");
            assertTrue(central >= 0);
            // CEN uncompressed size at +24. Zero is deliberately false.
            for (int i = 0; i < 4; i++) zip[central + 24 + i] = 0;
            Files.write(file.toPath(), zip);
            assertCorrupt(file);
        } finally { file.delete(); }
    }

    @Test public void perMemberAndAggregateInflationBudgetsAreEnforced()
            throws Exception {
        File file = fixture();
        try {
            writeFixture(file, true);
            try {
                ApkZipIntegrity.verify(file, 5, 1000,
                    ApkZipIntegrity.MAX_VERIFY_NANOS);
                fail("Per member budget must be checked before accepting");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("orçamento"));
            }
            try {
                ApkZipIntegrity.verify(file, 100, 30,
                    ApkZipIntegrity.MAX_VERIFY_NANOS);
                fail("Aggregate decompressed budget must be checked");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("orçamento"));
            }
        } finally { file.delete(); }
    }

    @Test public void cancellationRejectsEvenAValidZip() throws Exception {
        File file = fixture();
        try {
            writeFixture(file, false);
            Thread.currentThread().interrupt();
            try {
                ApkZipIntegrity.verify(file);
                fail("Interrupted ZIP audit cannot accept");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            } finally { Thread.interrupted(); }
        } finally { file.delete(); }
    }
}
