package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;
import java.io.InputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ApkImportPreflightInstrumentedTest {
    private static byte[] data(int count) {
        byte[] bytes = new byte[count];
        for (int i = 0; i < bytes.length; i++)
            bytes[i] = (byte) ((i * 17 + 23) & 255);
        return bytes;
    }

    private static String hexSha256(byte[] data) throws Exception {
        byte[] hash = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder result = new StringBuilder(64);
        for (byte value : hash)
            result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }

    @Test public void streamedShortReadsPreserveActualBytesAndHash() throws Exception {
        byte[] expected = data(257 * 1024 + 13);
        ByteArrayInputStream input = new ByteArrayInputStream(expected) {
            @Override public synchronized int read(byte[] buffer, int offset, int length) {
                return super.read(buffer, offset, Math.min(11, length));
            }
        };
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        AtomicInteger checks = new AtomicInteger();
        ApkImportPreflight.CopyResult result = ApkImportPreflight.copyAndHash(
            input, output, () -> {
                checks.incrementAndGet();
                return 128L * 1024 * 1024;
            });
        assertEquals(expected.length, result.sizeBytes);
        assertEquals(hexSha256(expected), result.sha256);
        assertArrayEquals(expected, output.toByteArray());
        assertEquals("Must check before streaming and on EOF", 2, checks.get());
    }

    @Test public void transientZeroReadsAreToleratedButStalledProviderIsRejected()
            throws Exception {
        byte[] expected = "small APK stream fixture".getBytes(StandardCharsets.UTF_8);
        ByteArrayInputStream source = new ByteArrayInputStream(expected) {
            int remainingZeros = 2;
            @Override public synchronized int read(byte[] bytes, int off, int len) {
                if (remainingZeros-- > 0) return 0;
                return super.read(bytes, off, len);
            }
        };
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        ApkImportPreflight.CopyResult ok =
            ApkImportPreflight.copyAndHash(source, output,
                () -> 100L * 1024 * 1024);
        assertEquals(expected.length, ok.sizeBytes);
        assertArrayEquals(expected, output.toByteArray());

        InputStream stalled = new InputStream() {
            @Override public int read() { return 0; }
            @Override public int read(byte[] bytes, int off, int len) { return 0; }
        };
        ByteArrayOutputStream untouched = new ByteArrayOutputStream();
        try {
            ApkImportPreflight.copyAndHash(stalled, untouched,
                () -> 100L * 1024 * 1024);
            fail("Repeated zero bytes cannot trap the import worker forever");
        } catch (IOException expectedError) {
            assertTrue(expectedError.getMessage().contains("parou de fornecer dados"));
            assertEquals(0, untouched.size());
        }
    }

    @Test public void finalDiskCheckRejectsSmallCopyWithoutSafetyReserve()
            throws Exception {
        byte[] expected = data(1024);
        AtomicInteger checks = new AtomicInteger();
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try {
            ApkImportPreflight.copyAndHash(
                new ByteArrayInputStream(expected), output,
                () -> checks.getAndIncrement() == 0
                    ? 65L * 1024 * 1024
                    : 63L * 1024 * 1024);
            fail("EOF must recheck free space even below the 32 MiB interval");
        } catch (IOException full) {
            assertTrue(full.getMessage().contains("pouco espaço"));
            assertEquals(2, checks.get());
            assertArrayEquals(expected, output.toByteArray());
        }
    }

    @Test public void emptyOrInterruptedSourceCannotReturnSuccess() throws Exception {
        try {
            ApkImportPreflight.copyAndHash(
                new ByteArrayInputStream(new byte[0]),
                new ByteArrayOutputStream(), () -> 100L * 1024 * 1024);
            fail("Zero bytes are never a valid APK import");
        } catch (IOException empty) {
            assertTrue(empty.getMessage().contains("vazio"));
        }
        ByteArrayOutputStream target = new ByteArrayOutputStream();
        Thread.currentThread().interrupt();
        try {
            ApkImportPreflight.copyAndHash(
                new ByteArrayInputStream(data(64)), target,
                () -> 100L * 1024 * 1024);
            fail("Cancelled import must not return success");
        } catch (java.io.InterruptedIOException expected) {
            assertEquals(0, target.size());
        } finally {
            Thread.interrupted(); // Clear only this test thread's flag.
        }
    }

    @Test public void midStreamProviderFailureCannotReturnSuccess() throws Exception {
        InputStream source = new InputStream() {
            private int count;
            @Override public int read() throws IOException {
                if (++count > 8) throw new IOException("Provedor parou no meio do arquivo");
                return 0x4d;
            }
            @Override public int read(byte[] bytes, int off, int len)
                    throws IOException {
                if (count >= 8) throw new IOException("Provedor parou no meio do arquivo");
                int n = Math.min(len, 8 - count);
                for (int i = 0; i < n; i++) bytes[off + i] = 0x4d;
                count += n;
                return n;
            }
        };
        ByteArrayOutputStream partial = new ByteArrayOutputStream();
        try {
            ApkImportPreflight.copyAndHash(source, partial,
                () -> 100L * 1024 * 1024);
            fail("An I/O exception after partial copy must fail the import");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Provedor parou"));
            assertEquals(8, partial.size());
        }
    }

    @Test public void apkLargerThanOneGiBIsRejectedBeforeCopy() throws Exception {
        try {
            ApkImportPreflight.checkClaimedSize(1024L * 1024 * 1024 + 1,
                4L * 1024 * 1024 * 1024);
            fail("Multi-GB imports should not be enabled without infrastructure");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("multi-GB"));
        }
    }

    @Test public void claimedSizeCannotConsumeAllAvailableStorage() throws Exception {
        try {
            ApkImportPreflight.checkClaimedSize(128L * 1024 * 1024,
                160L * 1024 * 1024);
            fail("No safety reserve");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Espaço insuficiente"));
        }
    }

    @Test public void unknownSizeStillNeedsReserveAndRuntimeLimit() throws Exception {
        ApkImportPreflight.checkClaimedSize(-1, 256L * 1024 * 1024);
        ApkImportPreflight.checkProgress(16L * 1024 * 1024, 90L * 1024 * 1024);
        try {
            ApkImportPreflight.checkProgress(1024L * 1024 * 1024 + 1,
                4L * 1024 * 1024 * 1024);
            fail("Actual streamed content must be bounded");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("1 GiB"));
        }
    }

    @Test public void periodicDiskChecksAvoidPerChunkStatCalls() {
        assertFalse(ApkImportPreflight.shouldRecheck(30L * 1024 * 1024, 0));
        assertTrue(ApkImportPreflight.shouldRecheck(32L * 1024 * 1024, 0));
        assertFalse(ApkImportPreflight.shouldRecheck(40L * 1024 * 1024,
            32L * 1024 * 1024));
    }
}
