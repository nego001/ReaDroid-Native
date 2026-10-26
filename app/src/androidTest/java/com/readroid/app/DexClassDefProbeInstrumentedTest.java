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
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M3.3: class_def numeric preview is bounded and never parses method bodies. */
@RunWith(AndroidJUnit4.class)
public final class DexClassDefProbeInstrumentedTest {
    private static void u32(byte[] data, int at, long n) {
        for (int j = 0; j < 4; j++)
            data[at + j] = (byte) (n >>> (8 * j));
    }

    private static void mapItem(byte[] dex, int entry, int type,
            long count, long offset, int mapOffset) {
        int at = mapOffset + 4 + 12 * entry;
        dex[at] = (byte) type;
        dex[at + 1] = (byte) (type >>> 8);
        u32(dex, at + 4, count);
        u32(dex, at + 8, offset);
    }

    private static byte[] fixture(int classCount) {
        int typeCount = Math.max(3, classCount + 2);
        int typeOff = 120;
        int classOff = typeOff + typeCount * 4;
        int mapOff = classOff + classCount * 32;
        int fileSize = Math.max(512, mapOff + 96);
        byte[] dex = new byte[fileSize];
        dex[0] = 'd'; dex[1] = 'e'; dex[2] = 'x'; dex[3] = 10;
        dex[4] = '0'; dex[5] = '3'; dex[6] = '9';
        u32(dex, 32, fileSize);
        u32(dex, 36, 112);
        u32(dex, 40, 0x12345678L);
        u32(dex, 52, mapOff);
        u32(dex, 56, 2); u32(dex, 60, 112);
        u32(dex, 64, typeCount); u32(dex, 68, typeOff);
        u32(dex, 96, classCount);
        u32(dex, 100, classCount == 0 ? 0 : classOff);
        u32(dex, 104, fileSize - mapOff);
        u32(dex, 108, mapOff);
        if (classCount > 0) {
            for (int i = 0; i < classCount; i++) {
                int at = classOff + i * 32;
                u32(dex, at, i); // sorted, unique class_idx
                u32(dex, at + 4, 1); // access flags
                u32(dex, at + 8, 0xffffffffL); // NO_INDEX superclass
                u32(dex, at + 16, 1); // source file string index
                u32(dex, at + 24, mapOff + 80); // class data is in data region
            }
        }
        // Coherent header + map declaration for the M3.2 predecessor.
        int mapItems = classCount == 0 ? 4 : 5;
        u32(dex, mapOff, mapItems);
        mapItem(dex, 0, 0, 1, 0, mapOff);
        mapItem(dex, 1, 1, 2, 112, mapOff);
        mapItem(dex, 2, 2, typeCount, typeOff, mapOff);
        if (classCount > 0)
            mapItem(dex, 3, 6, classCount, classOff, mapOff);
        mapItem(dex, mapItems - 1, 0x1000, 1, mapOff, mapOff);
        return dex;
    }

    private static void rejected(byte[] dex, long declaredLength)
            throws Exception {
        try {
            DexClassDefProbe.inspect(new ByteArrayInputStream(dex), declaredLength);
            fail("Malformed DEX class definitions must be rejected");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void validSortedClassIndicesStayNumericAndReadOnly()
            throws Exception {
        byte[] dex = fixture(2);
        byte[] original = dex.clone();
        DexClassDefProbe.Result report =
            DexClassDefProbe.inspect(new ByteArrayInputStream(dex), dex.length);
        assertEquals("039", report.version);
        assertEquals(2L, report.declaredClasses);
        assertEquals(2, report.items.size());
        assertFalse(report.previewTruncated);
        assertEquals(0L, report.items.get(0).classTypeIdx);
        assertEquals(1L, report.items.get(1).classTypeIdx);
        assertEquals(0xffffffffL, report.items.get(0).superclassTypeIdx);
        assertArrayEquals(original, dex);
    }

    @Test public void emptyClassTableAndPreviewCapAreExplicit()
            throws Exception {
        byte[] empty = fixture(0);
        DexClassDefProbe.Result none = DexClassDefProbe.inspect(
            new ByteArrayInputStream(empty), empty.length);
        assertEquals(0L, none.declaredClasses);
        assertTrue(none.items.isEmpty());
        byte[] large = fixture(26);
        DexClassDefProbe.Result sample = DexClassDefProbe.inspect(
            new ByteArrayInputStream(large), large.length);
        assertEquals(26L, sample.declaredClasses);
        assertEquals(24, sample.items.size());
        assertTrue(sample.previewTruncated);
        try {
            sample.items.add(sample.items.get(0));
            fail("Class-def result must be immutable");
        } catch (UnsupportedOperationException expected) {
            assertTrue(true);
        }
    }

    @Test public void rejectedTypeIndicesAndUnsortedOrDuplicateClasses()
            throws Exception {
        byte[] dex = fixture(2);
        int first = 120 + Math.max(3, 4) * 4;
        u32(dex, first, 4); // >= typeIds
        rejected(dex, dex.length);
        dex = fixture(2);
        u32(dex, first + 32, 0); // duplicate/lower class_idx
        rejected(dex, dex.length);
        dex = fixture(1);
        first = 120 + 3 * 4;
        u32(dex, first + 8, 3); // superclass index out of bounds
        rejected(dex, dex.length);
        dex = fixture(1);
        u32(dex, first + 16, 2); // sourceFile string index out of bounds
        rejected(dex, dex.length);
    }

    @Test public void rejectedDataOffsetsAndMisalignedInterfaces()
            throws Exception {
        byte[] dex = fixture(1);
        int at = 132;
        u32(dex, at + 24, 160); // class_data before data region
        rejected(dex, dex.length);
        dex = fixture(1);
        u32(dex, at + 24, dex.length); // class_data at EOF
        rejected(dex, dex.length);
        dex = fixture(1);
        u32(dex, at + 12, 201); // misaligned type_list
        rejected(dex, dex.length);
        dex = fixture(1);
        u32(dex, at + 20, 170); // misaligned annotations_directory
        rejected(dex, dex.length);
    }

    @Test public void truncatedClassRecordIsRejectedAndReaderStopsAtPreview()
            throws Exception {
        byte[] dex = fixture(2);
        rejected(Arrays.copyOf(dex, 150), dex.length);
        final int classTableEnd = 120 + 4 * 4 + 2 * 32;
        final int[] consumed = {0};
        InputStream input = new ByteArrayInputStream(dex) {
            @Override public synchronized int read(byte[] out, int off, int len) {
                if (consumed[0] >= classTableEnd)
                    throw new AssertionError("Unexpected read beyond class_def preview");
                int n = super.read(out, off, Math.min(len, classTableEnd - consumed[0]));
                if (n > 0) consumed[0] += n;
                return n;
            }
        };
        assertEquals(2, DexClassDefProbe.inspect(input, dex.length).items.size());
        assertEquals(classTableEnd, consumed[0]);
    }

    @Test public void distantClassTableRejectedBeforeStreamingBody()
            throws Exception {
        byte[] dex = fixture(1);
        long oversized = DexClassDefProbe.MAX_CLASS_TABLE_OFFSET + 2048L;
        u32(dex, 32, oversized);
        u32(dex, 100, DexClassDefProbe.MAX_CLASS_TABLE_OFFSET + 4);
        u32(dex, 104, oversized - 164);
        try {
            DexClassDefProbe.inspect(new ByteArrayInputStream(dex), oversized);
            fail("Distant class section must not be streamed");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("orçamento"));
        }
    }

    @Test public void cancellationPreservesInterruptFlag()
            throws Exception {
        byte[] dex = fixture(1);
        Thread.currentThread().interrupt();
        try {
            DexClassDefProbe.inspect(new ByteArrayInputStream(dex), dex.length);
            fail("Interrupted parsing must be cancelled");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(Thread.currentThread().isInterrupted());
        } finally { Thread.interrupted(); }
    }

    @Test public void scannerSurvivesMalformedDexAndBoundsClassPreview()
            throws Exception {
        File apk = File.createTempFile("readroid_m3_class_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                zip.putNextEntry(new ZipEntry("classes.dex"));
                zip.write(fixture(26)); zip.closeEntry();
                zip.putNextEntry(new ZipEntry("classes2.dex"));
                zip.write(new byte[]{'N', 'O', 'T'}); zip.closeEntry();
            }
            try (ZipFile zip = new ZipFile(apk)) {
                JSONObject report = SecurityScanner.scan(zip);
                JSONArray previews = report.getJSONArray("dexClassPreview");
                assertEquals(2, previews.length());
                JSONObject first = previews.getJSONObject(0);
                assertEquals("class-index-only", first.getString("status"));
                assertEquals(26, first.getLong("declaredClasses"));
                assertEquals(24, first.getJSONArray("classDefinitions").length());
                assertTrue(first.getBoolean("previewTruncated"));
                assertEquals("unreadable-class-index", previews.getJSONObject(1).getString("status"));
                assertFalse(report.getBoolean("dexClassPreviewTruncated"));
            }
        } finally { apk.delete(); }
    }
}
