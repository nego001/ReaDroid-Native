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
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import static org.junit.Assert.*;

/** Read-only streaming primitive, not evidence of processing a real 500 GB APK. */
@RunWith(AndroidJUnit4.class)
public final class StreamingFileProbeInstrumentedTest {
    private static String sha256(byte[] bytes) throws Exception {
        MessageDigest sha = MessageDigest.getInstance("SHA-256");
        byte[] result = sha.digest(bytes);
        StringBuilder text = new StringBuilder(64);
        for (byte b : result) text.append(String.format(Locale.ROOT, "%02x", b & 255));
        return text.toString();
    }

    @Test public void hashesMultiChunkSafDocumentWithoutCreatingASecondFile()
            throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File source = File.createTempFile("negresco_stream_", ".bin", context.getCacheDir());
        try {
            byte[] data = new byte[5 * 1024 * 1024 + 37];
            for (int i = 0; i < data.length; i++)
                data[i] = (byte) (i * 31 + 7);
            Files.write(source.toPath(), data);
            byte[] before = Files.readAllBytes(source.toPath());
            List<Long> progress = new ArrayList<>();
            StreamingFileProbe.Result result = StreamingFileProbe.inspect(
                context.getContentResolver(), Uri.fromFile(source),
                6L * 1024 * 1024, progress::add);
            assertEquals(data.length, result.bytesRead);
            assertEquals(sha256(data), result.sha256);
            assertArrayEquals(before, Files.readAllBytes(source.toPath()));
            assertTrue("Progress should report a 4 MiB checkpoint", progress.size() >= 2);
            assertEquals(Long.valueOf(data.length), progress.get(progress.size() - 1));
        } finally {
            source.delete();
        }
    }

    @Test public void rejectsInputExceedingApprovedBudget() throws Exception {
        byte[] data = new byte[131073];
        try {
            StreamingFileProbe.inspect(new ByteArrayInputStream(data), 131072, null);
            fail("Must never silently exceed the approved byte budget");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Limite autorizado"));
        }
    }

    @Test public void rejectsUnknownOrInvalidPermissionsAndBudgets() throws Exception {
        try {
            StreamingFileProbe.inspect(new ByteArrayInputStream(new byte[3]), 0, null);
            fail("Zero-byte budget is unsafe");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("positivo"));
        }
        assertEquals(0L, StreamingFileProbe.inspect(
            new ByteArrayInputStream(new byte[0]), 1024, null).bytesRead);
    }

    @Test public void aLargeLongBudgetDoesNotRequireAllocatingThatAmount()
            throws Exception {
        long fiveHundredGb = 500L * 1000 * 1000 * 1000;
        StreamingFileProbe.Result result = StreamingFileProbe.inspect(
            new ByteArrayInputStream(new byte[]{1, 2, 3}), fiveHundredGb, null);
        assertEquals(3L, result.bytesRead);
        // Large policy value != evidence a 500 GB file has been processed.
    }

    @Test public void cancellationStopsReadingBeforeConsumingInput()
            throws Exception {
        Thread.currentThread().interrupt();
        try {
            StreamingFileProbe.inspect(
                new ByteArrayInputStream(new byte[100]), 1024, null);
            fail("A cancelled worker cannot continue reading");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(expected.getMessage().contains("cancelada"));
        } finally {
            Thread.interrupted(); // Clear test thread state.
        }
    }
}
