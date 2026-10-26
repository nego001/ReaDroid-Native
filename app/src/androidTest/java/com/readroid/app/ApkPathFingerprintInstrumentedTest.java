package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M2.5: attacker-controlled long ZIP names are not kept in the heap. */
@RunWith(AndroidJUnit4.class)
public final class ApkPathFingerprintInstrumentedTest {
    @Test public void exactDuplicateIsRejectedIncludingUnicode() throws Exception {
        ApkPathFingerprintSet paths = new ApkPathFingerprintSet();
        paths.requireUnique("assets/Ônibus/São_João.txt");
        paths.requireUnique("assets/onibus/Sao_Joao.txt");
        assertEquals(2, paths.size());
        try {
            paths.requireUnique("assets/Ônibus/São_João.txt");
            fail("Identical path must not be admitted twice");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("duplicada"));
        }
        assertEquals(2, paths.size());
    }

    @Test public void manyLongNamesRemainDistinctWithoutRetainingStrings()
            throws Exception {
        ApkPathFingerprintSet paths = new ApkPathFingerprintSet();
        String common = "assets/series/" + repeat("p", 480);
        for (int i = 0; i < 8192; i++)
            paths.requireUnique(common + String.format(Locale.ROOT, "_%05d.bin", i));
        assertEquals(8192, paths.size());
        try {
            paths.requireUnique(common + "_08191.bin");
            fail("Duplicate at end of large corpus not identified");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("duplicada"));
        }
    }

    @Test public void allDistinctNamesStayCaseSensitive() throws Exception {
        ApkPathFingerprintSet paths = new ApkPathFingerprintSet();
        paths.requireUnique("assets/A.json");
        paths.requireUnique("assets/a.json");
        paths.requireUnique("assets/á.json");
        paths.requireUnique("assets/á.json");
        assertEquals(4, paths.size());
    }

    @Test public void longNameZipIsVerifiedWithExactSourcePreserved()
            throws Exception {
        File apk = File.createTempFile("readroid_fingerprint_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            String common = "assets/" + repeat("segment", 48) + "/";
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                for (int i = 0; i < 1024; i++) {
                    zip.putNextEntry(new ZipEntry(common +
                        String.format(Locale.ROOT, "trip_%04d.json", i)));
                    zip.write(new byte[]{'o', 'k'});
                    zip.closeEntry();
                }
            }
            byte[] before = Files.readAllBytes(apk.toPath());
            ApkArchiveSafety.Stats result = ApkArchiveSafety.verify(apk);
            assertEquals(1024, result.entries);
            assertEquals(1024, result.files);
            assertEquals(2048L, result.inflatedBytes);
            assertArrayEquals(before, Files.readAllBytes(apk.toPath()));
        } finally { apk.delete(); }
    }

    private static String repeat(String value, int copies) {
        StringBuilder out = new StringBuilder(value.length() * copies);
        for (int i = 0; i < copies; i++) out.append(value);
        return out.toString();
    }
}
