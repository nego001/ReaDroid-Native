package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Protect path-depth, single-name and aggregate metadata budgets in real ZipFile. */
@RunWith(AndroidJUnit4.class)
public final class ApkPathBudgetInstrumentedTest {
    private File temp() throws Exception {
        return File.createTempFile("readroid_pathbudget_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
    }

    private static void append(ZipOutputStream zip, String path) throws Exception {
        zip.putNextEntry(new ZipEntry(path));
        zip.closeEntry();
    }

    private static String repeated(int chars) {
        char[] values = new char[chars];
        java.util.Arrays.fill(values, 'p');
        return new String(values);
    }

    @Test public void oversizedSingleNameIsRejectedWithoutExtraction()
            throws Exception {
        File apk = temp();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                append(zip, "assets/" + repeated(4097) + ".bin");
            }
            try {
                ApkArchiveSafety.verify(apk);
                fail("ZIP entry name longer than 4096 must not be accepted");
            } catch (IOException expected) {
                assertNotNull(expected.getMessage());
            }
        } finally { apk.delete(); }
    }

    @Test public void aggregatePathBudgetRejectsOverSixteenMiCharacters()
            throws Exception {
        final int names = 16385;
        final int charCount = 1024;
        String prefix = "assets/" + repeated(charCount - 7 - 5 - 4);
        assertEquals(charCount - 9, prefix.length());
        File apk = temp();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                for (int i = 0; i < names; i++) {
                    String path = prefix + String.format(Locale.ROOT, "%05d", i) + ".bin";
                    assertEquals(charCount, path.length());
                    append(zip, path);
                }
            }
            assertTrue("Fixture unexpectedly over 1 GiB", apk.length() < (1L << 30));
            try {
                ApkArchiveSafety.verify(apk);
                fail("Total path characters above 16 Mi chars must be blocked");
            } catch (IOException expected) {
                assertTrue("Wrong admission failure: " + expected.getMessage(),
                    expected.getMessage().contains("orçamento de memória"));
            }
        } finally { apk.delete(); }
    }
}
