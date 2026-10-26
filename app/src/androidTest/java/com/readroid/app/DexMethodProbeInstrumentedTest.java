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
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** DEX method_id_item header + reference tests, not a method body parser. */
@RunWith(AndroidJUnit4.class)
public final class DexMethodProbeInstrumentedTest {
    private static void u32(byte[] data, int at, long value) {
        for (int i = 0; i < 4; i++) data[at + i] = (byte) (value >>> (8 * i));
    }

    private static void u16(byte[] data, int at, int value) {
        data[at] = (byte) value;
        data[at + 1] = (byte) (value >>> 8);
    }

    private static void mapItem(byte[] dex, int index, int type, int count, int off) {
        int at = 516 + index * 12;
        u16(dex, at, type);
        u32(dex, at + 4, count);
        u32(dex, at + 8, off);
    }

    /** Deliberately synthetic metadata, not a DEX executable. */
    private static byte[] fixture(String... methodNames) {
        int count = methodNames.length, stringCount = count + 1;
        int stringOff = 112, typeOff = stringOff + stringCount * 4;
        int protoOff = typeOff + 4, methodOff = protoOff + 12;
        int firstString = 620, perString = 192;
        byte[] dex = new byte[firstString + (count + 1) * perString + 16];
        dex[0]='d'; dex[1]='e'; dex[2]='x'; dex[3]=10;
        dex[4]='0'; dex[5]='3'; dex[6]='9';
        u32(dex, 32, dex.length);
        u32(dex, 36, 112);
        u32(dex, 40, 0x12345678L);
        u32(dex, 52, 512);
        u32(dex, 56, stringCount); u32(dex, 60, stringOff);
        u32(dex, 64, 1); u32(dex, 68, typeOff);
        u32(dex, 72, 1); u32(dex, 76, protoOff);
        u32(dex, 88, count); u32(dex, 92, count == 0 ? 0 : methodOff);
        u32(dex, 104, dex.length - 512); u32(dex, 108, 512);
        u32(dex, 512, 6);
        mapItem(dex, 0, 0, 1, 0);
        mapItem(dex, 1, 1, stringCount, stringOff);
        mapItem(dex, 2, 2, 1, typeOff);
        mapItem(dex, 3, 3, 1, protoOff);
        if (count > 0) {
            // Last two sections in this artificial map are not asserted
            // by the method probe and do not represent full DEX validity.
            mapItem(dex, 4, 5, count, methodOff);
        } else {
            mapItem(dex, 4, 0x1001, 1, 480);
        }
        mapItem(dex, 5, 0x1000, 1, 512);
        String[] data = new String[stringCount];
        data[0] = "Lapp/Example;";
        System.arraycopy(methodNames, 0, data, 1, count);
        for (int i = 0; i < stringCount; i++) {
            int at = firstString + i * perString;
            u32(dex, stringOff + 4 * i, at);
            byte[] utf8 = data[i].getBytes(StandardCharsets.UTF_8);
            if (utf8.length >= 180 || data[i].length() >= 128)
                throw new IllegalArgumentException("Invalid synthetic fixture");
            dex[at] = (byte) data[i].length();
            System.arraycopy(utf8, 0, dex, at + 1, utf8.length);
        }
        for (int i = 0; i < count; i++) {
            int at = methodOff + 8 * i;
            u16(dex, at, 0); // declaring type
            u16(dex, at + 2, 0); // prototype
            u32(dex, at + 4, i + 1); // sorted string indices
        }
        return dex;
    }

    private static int methodOff(int names) {
        return 112 + (names + 1) * 4 + 4 + 12;
    }

    private static DexMethodProbe.Result probe(byte[] bytes) throws Exception {
        return DexMethodProbe.inspect(() -> new ByteArrayInputStream(bytes), bytes.length);
    }

    private static void rejected(byte[] bytes) throws Exception {
        try {
            probe(bytes);
            fail("Malformed method_id reference should be rejected");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void readsSortedMethodsAndActualNamesWithoutModification()
            throws Exception {
        byte[] dex = fixture("<init>", "ação", "processar");
        byte[] before = dex.clone();
        DexMethodProbe.Result data = probe(dex);
        assertEquals("039", data.version);
        assertEquals(3L, data.totalMethodIds);
        assertEquals(3, data.methods.size());
        assertEquals("<init>", data.methods.get(0).name);
        assertEquals("ação", data.methods.get(1).name);
        assertEquals("processar", data.methods.get(2).name);
        assertEquals(0, data.methods.get(0).declaringTypeIdx);
        assertEquals(0, data.methods.get(1).prototypeIdx);
        assertEquals(2, data.methods.get(2).methodIndex);
        assertArrayEquals(before, dex);
    }

    @Test public void returnsAtMostEightMethodIdsAndMarksTruncation()
            throws Exception {
        String[] names = new String[10];
        for (int i = 0; i < names.length; i++) names[i] = "metodo" + i;
        DexMethodProbe.Result result = probe(fixture(names));
        assertEquals(10L, result.totalMethodIds);
        assertEquals(8, result.methods.size());
        assertTrue(result.truncated);
        try {
            result.methods.add(result.methods.get(0));
            fail("Preview should be immutable");
        } catch (UnsupportedOperationException expected) {
            assertTrue(true);
        }
        DexMethodProbe.Result empty = probe(fixture());
        assertEquals(0L, empty.totalMethodIds);
        assertEquals(0, empty.methods.size());
    }

    @Test public void rejectsIndexesOutsideStringTypeAndProtoTables()
            throws Exception {
        byte[] dex = fixture("start");
        int off = methodOff(1);
        u16(dex, off, 1); rejected(dex);
        dex = fixture("start");
        u16(dex, off + 2, 1); rejected(dex);
        dex = fixture("start");
        u32(dex, off + 4, 2); rejected(dex); // string_count=2, index=2
        dex = fixture("start");
        u32(dex, 112 + 4, dex.length); rejected(dex); // string_data_off EOF
    }

    @Test public void rejectsUnsortedOrDuplicateMethodIdEntries() throws Exception {
        byte[] dex = fixture("start", "stop");
        u32(dex, methodOff(2) + 8 + 4, 1); // same class/name/proto as first
        rejected(dex);
        dex = fixture("start", "stop");
        u32(dex, methodOff(2) + 4, 2);
        u32(dex, methodOff(2) + 8 + 4, 1);
        rejected(dex);
    }

    @Test public void rejectsMalformedNamesAndEarlyTerminator() throws Exception {
        byte[] dex = fixture("start");
        int at = 620 + 192;
        dex[at] = (byte) 0xff; rejected(dex);
        dex = fixture("start");
        dex[at + 1] = (byte) 0xff; rejected(dex);
        dex = fixture("start");
        dex[at + 2] = 0; rejected(dex);
        dex = fixture("start");
        dex[at + 1] = (byte) '/'; rejected(dex);
    }

    @Test public void blocksDistantMethodTableBeforeDecompression() throws Exception {
        byte[] dex = fixture("start");
        long length = DexMethodProbe.MAX_OFFSET + 4096;
        u32(dex, 32, length);
        u32(dex, 92, DexMethodProbe.MAX_OFFSET + 4);
        u32(dex, 104, length - 512);
        try {
            DexMethodProbe.inspect(() -> new ByteArrayInputStream(dex), length);
            fail("Distant method table must not be streamed");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("limite"));
        }
    }

    @Test public void truncatedAndCancelledSourcesFailClosed() throws Exception {
        byte[] dex = fixture("start");
        try {
            DexMethodProbe.inspect(
                () -> new ByteArrayInputStream(Arrays.copyOf(dex, 40)), dex.length);
            fail("Truncated DEX header should fail");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
        Thread.currentThread().interrupt();
        try {
            probe(dex);
            fail("Cancelled operation must not succeed");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(Thread.currentThread().isInterrupted());
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void scannerReportsNamesButDoesNotClaimMethodsAreImplemented()
            throws Exception {
        File apk = File.createTempFile("readroid_m35_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                zip.putNextEntry(new ZipEntry("classes.dex"));
                zip.write(fixture("<init>", "analisar")); zip.closeEntry();
                zip.putNextEntry(new ZipEntry("classes2.dex"));
                zip.write(new byte[]{'X', 'Y', 'Z'}); zip.closeEntry();
            }
            try (ZipFile zip = new ZipFile(apk)) {
                JSONObject report = SecurityScanner.scan(zip);
                JSONArray previews = report.getJSONArray("dexMethodPreview");
                assertEquals(2, previews.length());
                JSONObject good = previews.getJSONObject(0);
                assertEquals("method-ids-preview", good.getString("status"));
                assertEquals(2L, good.getLong("totalMethodIds"));
                assertEquals("analisar", good.getJSONArray("methodIds")
                    .getJSONObject(1).getString("methodName"));
                assertEquals("unreadable-method-ids",
                    previews.getJSONObject(1).getString("status"));
                assertFalse(report.getBoolean("dexMethodPreviewTruncated"));
                assertTrue(report.getString("limitations").contains("externos"));
            }
        } finally {
            apk.delete();
        }
    }
}
