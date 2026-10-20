package com.readroid.app;

import android.content.Context;
import android.net.Uri;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;

import static org.junit.Assert.*;

/** Synthetic-only bounded read probes; no claim to parse/decompile content. */
@RunWith(AndroidJUnit4.class)
public final class FileHeaderProbeInstrumentedTest {
    private static FileHeaderProbe.Result classify(int... values) throws Exception {
        byte[] data = new byte[values.length];
        for (int i = 0; i < values.length; i++) data[i] = (byte) values[i];
        return FileHeaderProbe.inspect(new ByteArrayInputStream(data));
    }

    @Test public void distinguishesZipElFAndMZWithoutClaimingAPKOrPEValidity()
            throws Exception {
        FileHeaderProbe.Result zip = classify(0x50, 0x4b, 0x03, 0x04, 0);
        assertEquals("ZIP", zip.format);
        assertTrue(zip.description.contains("não confirmado"));
        assertEquals("ELF", classify(0x7f, 0x45, 0x4c, 0x46).format);
        FileHeaderProbe.Result mz = classify(0x4d, 0x5a, 0, 0);
        assertEquals("MZ_CANDIDATE", mz.format);
        assertTrue(mz.description.contains("não confirmado"));
        assertEquals("DEX", classify(0x64, 0x65, 0x78, 0x0a).format);
        assertEquals("PNG", classify(0x89, 0x50, 0x4e, 0x47,
            0x0d, 0x0a, 0x1a, 0x0a).format);
    }

    @Test public void emptyOrUnknownHeaderIsNotInventedAsKnownFormat()
            throws Exception {
        assertEquals("UNKNOWN", classify().format);
        assertEquals("UNKNOWN", classify(0x50, 0x4b).format);
        assertEquals("UNKNOWN", classify(0x33, 0x55, 0x66).format);
    }

    @Test public void worksWithSafDocumentAndDoesNotModifyIt() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File file = File.createTempFile("readroid_header_", ".bin", context.getCacheDir());
        try {
            byte[] bytes = new byte[]{0x50, 0x4b, 0x03, 0x04, 20, 10};
            Files.write(file.toPath(), bytes);
            FileHeaderProbe.Result result = FileHeaderProbe.inspect(
                context.getContentResolver(), Uri.fromFile(file));
            assertEquals("ZIP", result.format);
            assertArrayEquals(bytes, Files.readAllBytes(file.toPath()));
        } finally {
            file.delete();
        }
    }

    @Test public void limitsReadToSixtyFourBytesAndHandlesPartialReads()
            throws Exception {
        byte[] bytes = new byte[1024 * 1024];
        bytes[0] = 0x50; bytes[1] = 0x4b;
        bytes[2] = 0x03; bytes[3] = 0x04;
        final int[] consumed = {0};
        InputStream partial = new ByteArrayInputStream(bytes) {
            @Override public synchronized int read(byte[] target, int offset, int length) {
                int n = super.read(target, offset, Math.min(3, length));
                if (n > 0) consumed[0] += n;
                return n;
            }
        };
        FileHeaderProbe.Result result = FileHeaderProbe.inspect(partial);
        assertEquals(64, result.sampleBytes);
        assertEquals(64, consumed[0]);
        assertEquals("ZIP", result.format);
    }

    @Test public void cancellationIsFailClosed() throws Exception {
        Thread.currentThread().interrupt();
        try {
            FileHeaderProbe.inspect(new ByteArrayInputStream(new byte[]{0x4d, 0x5a}));
            fail("Cancelled probe must not produce evidence");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(expected.getMessage().contains("cancelada"));
        } finally {
            Thread.interrupted();
        }
    }
}
