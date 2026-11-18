package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/**
 * Only NON-DESTRUCTIVE ZIP checks run inside AndroidJUnitRunner.
 * F1.30 real remote provider death is executed by a host-driven debug
 * harness after instrumented tests, so the test runner itself is never killed.
 */
@RunWith(AndroidJUnit4.class)
public final class F130ProviderDeathInstrumentedTest {
    private static byte[] completeZip() throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(buffer)) {
            for (String entry : new String[]{
                    "AndroidManifest.xml", "assets/important.dat"}) {
                zip.putNextEntry(new ZipEntry(entry));
                zip.write(("valid content of " + entry).getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        }
        return buffer.toByteArray();
    }

    @Test public void f130ValidLocalEntriesButMissingZipEndAreRejected()
            throws Exception {
        File dir = Files.createTempDirectory(
            InstrumentationRegistry.getInstrumentation().getTargetContext()
                .getCacheDir().toPath(), "f130_zip_").toFile();
        File source = new File(dir, "original_reference.zip");
        ImportActivityScope scope = new ImportActivityScope(dir);
        File candidate = null;
        try {
            byte[] entire = completeZip();
            Files.write(source.toPath(), entire);
            assertEquals("Intact archive should pass the ZIP auditor", 2,
                ApkZipIntegrity.verify(source).verifiedFiles);
            // Leave valid local headers and central entries but remove the
            // End of Central Directory. The streamed SHA-256 alone is not
            // sufficient evidence for accepting an APK.
            assertTrue(entire.length > 100);
            byte[] truncated = Arrays.copyOf(entire, entire.length - 22);
            ApkImportStaging.Result result = ApkImportStaging.copy(dir,
                () -> new ByteArrayInputStream(truncated),
                () -> 128L * 1024 * 1024, null, scope);
            candidate = result.candidate;
            assertEquals(truncated.length, result.copied.sizeBytes);
            assertTrue(candidate.getName().endsWith(".apk"));
            assertArrayEquals(truncated, Files.readAllBytes(candidate.toPath()));
            try {
                ApkZipIntegrity.verify(candidate);
                fail("An incomplete EOCD must never reach project acceptance");
            } catch (IOException correct) {
                assertNotNull(correct.getMessage());
            }
        } finally {
            scope.close();
            if (candidate != null) {
                ImportCacheAudit.release(candidate);
                candidate.delete();
            }
            source.delete();
            File[] remaining = dir.listFiles();
            if (remaining != null)
                for (File file : remaining) file.delete();
            dir.delete();
        }
    }
}
