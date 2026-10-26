package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

/** Actual stream behavior with simulated broken SAF content providers. */
@RunWith(AndroidJUnit4.class)
public final class SafImportStreamInstrumentedTest {
    private static final long FREE = 256L * 1024 * 1024;

    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format("%02x", b & 255));
        return out.toString();
    }

    @Test public void validUnknownSizeStreamsAndReturnsExactHash()
            throws Exception {
        byte[] bytes = "APK M2 stream".getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        SafImportStream.Result r = SafImportStream.copyAndHash(
            new ByteArrayInputStream(bytes), out, () -> FREE, 1024);
        assertEquals(bytes.length, r.bytesCopied);
        assertArrayEquals(bytes, out.toByteArray());
        assertEquals(hex(MessageDigest.getInstance("SHA-256").digest(bytes)), r.sha256);
    }

    @Test public void exactBoundaryIsAllowedAfterSentinelRead()
            throws Exception {
        byte[] bytes = new byte[13];
        Arrays.fill(bytes, (byte) 7);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        SafImportStream.Result r = SafImportStream.copyAndHash(
            new ByteArrayInputStream(bytes), out, () -> FREE, 13);
        assertEquals(13, r.bytesCopied);
        assertArrayEquals(bytes, out.toByteArray());
    }

    @Test public void oneBytePastLimitIsRejectedAndNotWritten()
            throws Exception {
        byte[] bytes = new byte[14];
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            SafImportStream.copyAndHash(
                new ByteArrayInputStream(bytes), out, () -> FREE, 13);
            fail("Provider understated size should never bypass max bytes");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("limite"));
        }
        assertTrue(out.size() <= 13);
    }

    @Test public void repeatedZeroReadsTerminateDeterministically()
            throws Exception {
        AtomicInteger reads = new AtomicInteger();
        InputStream bad = new InputStream() {
            @Override public int read() { reads.incrementAndGet(); return 0; }
            @Override public int read(byte[] b, int off, int len) {
                reads.incrementAndGet();
                return 0;
            }
        };
        try {
            SafImportStream.copyAndHash(bad, new ByteArrayOutputStream(),
                () -> FREE, 100);
            fail("Non-progressing provider must not loop forever");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("parou"));
        }
        assertEquals(17, reads.get());
    }

    @Test public void intermittentZeroReadsAreTolerated()
            throws Exception {
        byte[] original = new byte[]{1, 2, 3};
        InputStream intermittent = new ByteArrayInputStream(original) {
            int calls;
            @Override public synchronized int read(byte[] b, int off, int len) {
                if (++calls <= 3) return 0;
                return super.read(b, off, len);
            }
        };
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        SafImportStream.Result r = SafImportStream.copyAndHash(
            intermittent, out, () -> FREE, 20);
        assertEquals(3, r.bytesCopied);
        assertArrayEquals(original, out.toByteArray());
    }

    @Test public void finalStorageCheckRunsEvenOnTinyFiles()
            throws Exception {
        AtomicInteger checks = new AtomicInteger();
        try {
            SafImportStream.copyAndHash(
                new ByteArrayInputStream(new byte[]{1, 2, 3}),
                new ByteArrayOutputStream(),
                () -> checks.incrementAndGet() == 1 ? FREE : 8L * 1024 * 1024,
                32);
            fail("Cache exhaustion after final write cannot be accepted");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("espaço"));
        }
        assertEquals(2, checks.get());
    }

    @Test public void insufficientSpaceBeforeCopyLeavesDestinationEmpty()
            throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try {
            SafImportStream.copyAndHash(
                new ByteArrayInputStream(new byte[]{1}), out,
                () -> 4L * 1024 * 1024, 20);
            fail("No writes permitted below storage reserve");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("espaço"));
        }
        assertEquals(0, out.size());
    }

    @Test public void interruptionPreservesFlagAndStopsBeforeRead()
            throws Exception {
        try {
            Thread.currentThread().interrupt();
            try {
                SafImportStream.copyAndHash(
                    new ByteArrayInputStream(new byte[]{1}),
                    new ByteArrayOutputStream(), () -> FREE, 20);
                fail("Interrupted import must fail");
            } catch (InterruptedIOException expected) {
                assertTrue(Thread.currentThread().isInterrupted());
            }
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void providerIOExceptionIsPropagatedWithoutSuccessHash()
            throws Exception {
        InputStream failing = new InputStream() {
            @Override public int read() throws IOException {
                throw new IOException("falha no provedor");
            }
            @Override public int read(byte[] b, int off, int len) throws IOException {
                throw new IOException("falha no provedor");
            }
        };
        try {
            SafImportStream.copyAndHash(failing,
                new ByteArrayOutputStream(), () -> FREE, 20);
            fail("Broken provider cannot produce accepted SHA-256");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("falha no provedor"));
        }
    }
}
