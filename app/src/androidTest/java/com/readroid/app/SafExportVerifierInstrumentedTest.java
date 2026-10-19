package com.readroid.app;

import android.content.Context;
import android.net.Uri;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;

import static org.junit.Assert.*;

/**
 * Checks byte-verified SAF export with file:// as a local ContentResolver target.
 * A full DocumentsUI flow is covered by the separate emulator UI smoke.
 */
@RunWith(AndroidJUnit4.class)
public final class SafExportVerifierInstrumentedTest {
    @Test public void copiesEveryByteAndConfirmsSha256() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File original = File.createTempFile("negresco_source_", ".apk", context.getCacheDir());
        File saved = File.createTempFile("negresco_dest_", ".apk", context.getCacheDir());
        try {
            byte[] bytes = new byte[257 * 1024 + 31];
            for (int index = 0; index < bytes.length; index++)
                bytes[index] = (byte) ((index * 37 + 17) & 255);
            Files.write(original.toPath(), bytes);
            long copied = SafExportVerifier.copyAndVerify(
                context.getContentResolver(), original, Uri.fromFile(saved));
            assertEquals(bytes.length, copied);
            assertArrayEquals(bytes, Files.readAllBytes(saved.toPath()));
            assertArrayEquals(bytes, Files.readAllBytes(original.toPath()));
        } finally {
            original.delete();
            saved.delete();
        }
    }

    @Test public void rejectsMissingSourceWithoutModifyingDestination() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File missing = new File(context.getCacheDir(), "nonexistent_source_edit_test.apk");
        File destination = File.createTempFile("negresco_untouched_", ".apk", context.getCacheDir());
        byte[] sentinel = new byte[]{1, 4, 9, 16};
        try {
            missing.delete();
            Files.write(destination.toPath(), sentinel);
            try {
                SafExportVerifier.copyAndVerify(
                    context.getContentResolver(), missing, Uri.fromFile(destination));
                fail("A missing source must not export");
            } catch (java.io.IOException expected) {
                assertArrayEquals(sentinel, Files.readAllBytes(destination.toPath()));
            }
        } finally {
            destination.delete();
        }
    }
}
