package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M3.1 only proves bounded DEX header inspection, not DEX body decoding. */
@RunWith(AndroidJUnit4.class)
public final class DexHeaderProbeInstrumentedTest {
    private static void write32(byte[] value, int offset, long n) {
        for (int i = 0; i < 4; i++)
            value[offset + i] = (byte) (n >>> (8 * i));
    }

    private static byte[] fixture(String version) {
        byte[] bytes = new byte[128];
        bytes[0] = 'd'; bytes[1] = 'e'; bytes[2] = 'x'; bytes[3] = 10;
        for (int i = 0; i < 3; i++) bytes[4+i] = (byte) version.charAt(i);
        bytes[7] = 0;
        write32(bytes, 32, bytes.length);
        write32(bytes, 36, 112);
        write32(bytes, 40, 0x12345678L);
        write32(bytes, 52, 112); // map_off
        write32(bytes, 104, 16); // data_size
        write32(bytes, 108, 112); // data_off
        // Header plausibility fixture, not a complete executable DEX.
        return bytes;
    }

    private static void rejected(byte[] data, long size) throws Exception {
        try {
            DexHeaderProbe.inspect(new ByteArrayInputStream(data), size);
            fail("Untrusted DEX header should not pass");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void supportedVersionsExposeOnlyBoundedNumericMetadata()
            throws Exception {
        for (String version : new String[]{"035", "039", "040"}) {
            byte[] data = fixture(version);
            DexHeaderProbe.Header result = DexHeaderProbe.inspect(
                new ByteArrayInputStream(data), data.length);
            assertEquals(version, result.version);
            assertEquals(128L, result.sizeBytes);
            assertEquals(0L, result.classDefs);
            assertEquals(0L, result.methodIds);
        }
    }

    @Test public void invalidVersionsMagicAndEndianFailClosed() throws Exception {
        byte[] wrong = fixture("041");
        rejected(wrong, wrong.length);
        wrong = fixture("039");
        wrong[0] = 'x'; rejected(wrong, wrong.length);
        wrong = fixture("039");
        write32(wrong, 40, 0x78563412L); rejected(wrong, wrong.length);
    }

    @Test public void bogusFileSizeHeaderSizeAndSectionsFailClosed()
            throws Exception {
        byte[] wrong = fixture("039");
        write32(wrong, 32, 65536); rejected(wrong, wrong.length);
        wrong = fixture("039");
        write32(wrong, 36, 120); rejected(wrong, wrong.length);
        wrong = fixture("039");
        write32(wrong, 56, 0xffffffffL); // string count overflow attack
        write32(wrong, 60, 116); rejected(wrong, wrong.length);
        wrong = fixture("039");
        write32(wrong, 96, 2); // 2*32 bytes extend past end
        write32(wrong, 100, 116); rejected(wrong, wrong.length);
        wrong = fixture("039");
        write32(wrong, 104, 0xffffffffL); rejected(wrong, wrong.length);
        wrong = fixture("039");
        write32(wrong, 52, 0); rejected(wrong, wrong.length);
    }

    @Test public void truncatedInputCannotReadBeyond112Bytes() throws Exception {
        byte[] data = fixture("035");
        rejected(java.util.Arrays.copyOf(data, 70), data.length);
        InputStream limit = new ByteArrayInputStream(data) {
            private int total;
            @Override public synchronized int read(byte[] b, int off, int len) {
                if (total >= 112) throw new AssertionError("DEX body read");
                int n = super.read(b, off, Math.min(len, 112 - total));
                if (n > 0) total += n;
                return n;
            }
        };
        assertEquals("035", DexHeaderProbe.inspect(limit, data.length).version);
    }

    @Test public void interruptionPreservesThreadFlag() throws Exception {
        byte[] data = fixture("035");
        Thread.currentThread().interrupt();
        try {
            DexHeaderProbe.inspect(new ByteArrayInputStream(data), data.length);
            fail("Cancelled DEX reader should stop");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(Thread.currentThread().isInterrupted());
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void scannerReportsValidAndRejectedDexWithoutCrashing()
            throws Exception {
        File zipFile = File.createTempFile("m3_dex_header_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(zipFile))) {
                ZipEntry good = new ZipEntry("classes.dex");
                out.putNextEntry(good);
                out.write(fixture("039"));
                out.closeEntry();
                out.putNextEntry(new ZipEntry("classes2.dex"));
                out.write(new byte[]{'x', 'y', 'z'});
                out.closeEntry();
            }
            try (ZipFile apk = new ZipFile(zipFile)) {
                JSONObject result = SecurityScanner.scan(apk);
                JSONArray headers = result.getJSONArray("dexHeaderPreview");
                assertEquals(2, result.getInt("dexFileCount"));
                assertEquals(2, headers.length());
                assertEquals("header-only", headers.getJSONObject(0).getString("status"));
                assertEquals("039", headers.getJSONObject(0).getString("version"));
                assertEquals("unreadable-header", headers.getJSONObject(1).getString("status"));
                assertFalse(result.getBoolean("dexHeaderPreviewTruncated"));
                assertFalse(result.toString().contains("DEX body"));
            }
        } finally {
            zipFile.delete();
        }
    }
}
