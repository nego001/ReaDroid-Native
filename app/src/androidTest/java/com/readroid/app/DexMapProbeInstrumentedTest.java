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
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M3.2 map_list verification is bounded, read-only, and never executes DEX. */
@RunWith(AndroidJUnit4.class)
public final class DexMapProbeInstrumentedTest {
    private static void u32(byte[] b, int at, long v) {
        for (int i = 0; i < 4; i++) b[at + i] = (byte) (v >>> (i * 8));
    }

    private static void u16(byte[] b, int at, int v) {
        b[at] = (byte) v;
        b[at + 1] = (byte) (v >>> 8);
    }

    private static void item(byte[] dex, int index, int type, long size,
            long offset) {
        int at = 132 + index * 12;
        u16(dex, at, type);
        u16(dex, at + 2, 0);
        u32(dex, at + 4, size);
        u32(dex, at + 8, offset);
    }

    private static byte[] fixture() {
        byte[] dex = new byte[256];
        dex[0] = 'd'; dex[1] = 'e'; dex[2] = 'x'; dex[3] = 10;
        dex[4] = '0'; dex[5] = '3'; dex[6] = '9';
        u32(dex, 32, dex.length);
        u32(dex, 36, 112);
        u32(dex, 40, 0x12345678L);
        u32(dex, 52, 128); // map_off
        u32(dex, 104, 144); // data_size
        u32(dex, 108, 112); // data_off
        u32(dex, 128, 2); // map_list length
        item(dex, 0, 0, 1, 0);
        item(dex, 1, 0x1000, 1, 128);
        return dex;
    }

    private static void rejected(byte[] data) throws Exception {
        try {
            DexMapProbe.inspect(new ByteArrayInputStream(data), data.length);
            fail("Mapa inválido não deve ser aceito");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void validMapListsOnlyHeaderAndMapWithoutReadingBody()
            throws Exception {
        byte[] dex = fixture();
        final int[] total = {0};
        InputStream guarded = new ByteArrayInputStream(dex) {
            @Override public synchronized int read(byte[] b, int off, int len) {
                if (total[0] >= 156)
                    throw new AssertionError("Leitura ultrapassou o fim do map_list");
                int n = super.read(b, off, Math.min(len, 156 - total[0]));
                if (n > 0) total[0] += n;
                return n;
            }
        };
        DexMapProbe.Result result = DexMapProbe.inspect(guarded, dex.length);
        assertEquals("039", result.version);
        assertEquals(128L, result.mapOffset);
        assertEquals(2, result.items.size());
        assertEquals("header", result.items.get(0).label);
        assertEquals("map_list", result.items.get(1).label);
        assertEquals(156, total[0]);
    }

    @Test public void headerAndMapMustAgreeOnTableCountsAndOffsets()
            throws Exception {
        byte[] data = fixture();
        // string_ids at 112, just before map at 128
        u32(data, 56, 1);
        u32(data, 60, 112);
        u32(data, 128, 3);
        item(data, 0, 0, 1, 0);
        item(data, 1, 1, 1, 112);
        item(data, 2, 0x1000, 1, 128);
        assertEquals(3, DexMapProbe.inspect(
            new ByteArrayInputStream(data), data.length).items.size());
        u32(data, 148, 2);
        rejected(data); // string_ids count disagrees with header
    }

    @Test public void rejectDuplicateTypeUnsortedOffsetsOrMissingMap()
            throws Exception {
        byte[] dex = fixture();
        item(dex, 1, 0, 1, 128);
        rejected(dex);
        dex = fixture(); item(dex, 1, 0x1000, 1, 0); rejected(dex);
        dex = fixture(); item(dex, 1, 0x1001, 1, 128); rejected(dex);
    }

    @Test public void rejectTruncatedMapAndForgedCountWithoutAllocation()
            throws Exception {
        byte[] dex = fixture();
        u32(dex, 128, 0xffffffffL);
        rejected(dex);
        dex = fixture();
        u32(dex, 128, 64);
        rejected(dex); // 64 map items cannot fit in remaining bytes
        dex = fixture();
        u32(dex, 152, 250); // map_list starts at 250, not at 128
        rejected(dex);
    }

    @Test public void rejectUnknownSectionTypeAndNonzeroReservedField()
            throws Exception {
        byte[] dex = fixture();
        item(dex, 1, 0xcccc, 1, 128); rejected(dex);
        dex = fixture();
        u16(dex, 146, 9);
        rejected(dex);
    }

    @Test public void mapBeyondReadBudgetIsRejectedWithoutAllocatingItsBody()
            throws Exception {
        byte[] header = fixture();
        long size = DexMapProbe.MAX_MAP_OFFSET + 512;
        u32(header, 32, size);
        u32(header, 52, DexMapProbe.MAX_MAP_OFFSET + 128);
        u32(header, 104, size - 112);
        try {
            DexMapProbe.inspect(new ByteArrayInputStream(header), size);
            fail("DEX must not read a distant map");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("orçamento"));
        }
    }

    @Test public void interruptedMapReadPropagatesAndPreservesFlag()
            throws Exception {
        Thread.currentThread().interrupt();
        try {
            DexMapProbe.inspect(new ByteArrayInputStream(fixture()), 256);
            fail("Cancelamento deve interromper leitura");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(Thread.currentThread().isInterrupted());
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void scannerListsOnlySafeMapMetadataAndSurvivesBadDex()
            throws Exception {
        File archive = File.createTempFile("readroid_m3_map_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(archive))) {
                out.putNextEntry(new ZipEntry("classes.dex"));
                out.write(fixture()); out.closeEntry();
                out.putNextEntry(new ZipEntry("classes2.dex"));
                out.write(new byte[]{'X', 'Y', 'Z'}); out.closeEntry();
            }
            try (ZipFile zip = new ZipFile(archive)) {
                JSONObject report = SecurityScanner.scan(zip);
                JSONArray maps = report.getJSONArray("dexMapPreview");
                assertEquals(2, maps.length());
                assertEquals("map-only", maps.getJSONObject(0).getString("status"));
                assertEquals(2, maps.getJSONObject(0).getInt("declaredSections"));
                assertEquals(2, maps.getJSONObject(0).getJSONArray("sections").length());
                assertEquals("unreadable-map", maps.getJSONObject(1).getString("status"));
                assertFalse(report.getBoolean("dexMapPreviewTruncated"));
                assertFalse(report.toString().contains("execute bytecode"));
            }
        } finally { archive.delete(); }
    }
}
