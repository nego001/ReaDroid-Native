package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ApkCacheAdmissionInstrumentedTest {
    private File tempApk() throws IOException {
        Context ctx = InstrumentationRegistry.getInstrumentation().getTargetContext();
        return File.createTempFile("f17_cache_", ".apk", ctx.getCacheDir());
    }

    private static byte[] payload() {
        return "F1.7 preserved bytes: SHA-256 anchored to the SAF copy"
            .getBytes(StandardCharsets.UTF_8);
    }

    private static ApkImportPreflight.CopyResult copy(File file) throws Exception {
        try (FileOutputStream out = new FileOutputStream(file)) {
            return ApkImportPreflight.copyAndHash(
                new ByteArrayInputStream(payload()), out,
                () -> 128L * 1024 * 1024);
        }
    }

    @Test public void acceptsExactPrivateCacheBytesAfterCopy() throws Exception {
        File file = tempApk();
        try {
            ApkImportPreflight.CopyResult result = copy(file);
            ApkCacheAdmission.verify(file, result.sizeBytes, result.sha256);
            assertEquals(payload().length, file.length());
        } finally { file.delete(); }
    }

    @Test public void rejectsSameLengthCacheMutationNotCaughtBySize()
            throws Exception {
        File file = tempApk();
        try {
            ApkImportPreflight.CopyResult result = copy(file);
            byte[] altered = Files.readAllBytes(file.toPath());
            altered[altered.length - 1] ^= 1;
            Files.write(file.toPath(), altered);
            try {
                ApkCacheAdmission.verify(file, result.sizeBytes, result.sha256);
                fail("Same-length corruption cannot be accepted");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Integridade"));
            }
        } finally { file.delete(); }
    }

    @Test public void rejectsTruncationAndAppendedBytes() throws Exception {
        File file = tempApk();
        try {
            ApkImportPreflight.CopyResult result = copy(file);
            byte[] original = Files.readAllBytes(file.toPath());
            Files.write(file.toPath(), java.util.Arrays.copyOf(original,
                original.length - 1));
            try {
                ApkCacheAdmission.verify(file, result.sizeBytes, result.sha256);
                fail("Truncation must be rejected");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Tamanho"));
            }
            Files.write(file.toPath(), java.util.Arrays.copyOf(original,
                original.length + 1));
            try {
                ApkCacheAdmission.verify(file, result.sizeBytes, result.sha256);
                fail("Appended byte must be rejected");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Tamanho"));
            }
        } finally { file.delete(); }
    }

    @Test public void rejectsUntrustedOrMissingExpectedMetadata()
            throws Exception {
        File file = tempApk();
        try {
            ApkImportPreflight.CopyResult result = copy(file);
            String[] invalid = {null, "", "deadbeef", result.sha256.toUpperCase()};
            for (String expectedHash : invalid) {
                try {
                    ApkCacheAdmission.verify(file, result.sizeBytes, expectedHash);
                    fail("Invalid SHA-256 metadata must not pass");
                } catch (IOException expected) {
                    assertTrue(expected.getMessage().contains("Metadados"));
                }
            }
            try {
                ApkCacheAdmission.verify(file, 0, result.sha256);
                fail("Invalid size metadata must not pass");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Metadados"));
            }
        } finally { file.delete(); }
    }

    @Test public void cancellationCannotAcceptMatchingCache()
            throws Exception {
        File file = tempApk();
        try {
            ApkImportPreflight.CopyResult result = copy(file);
            Thread.currentThread().interrupt();
            try {
                ApkCacheAdmission.verify(file, result.sizeBytes, result.sha256);
                fail("Canceled validation must be rejected");
            } catch (java.io.InterruptedIOException expected) {
                assertTrue(expected.getMessage().contains("interrompida"));
            } finally { Thread.interrupted(); }
        } finally { file.delete(); }
    }
}
