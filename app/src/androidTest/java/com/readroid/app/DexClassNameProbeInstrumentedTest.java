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
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M3.4 synthetic but structurally consistent class descriptor references. */
@RunWith(AndroidJUnit4.class)
public final class DexClassNameProbeInstrumentedTest {
    private static void u32(byte[] bytes, int at, long value) {
        for (int i = 0; i < 4; i++)
            bytes[at + i] = (byte) (value >>> (8 * i));
    }

    private static void mapItem(byte[] dex, int mapOff, int index,
            int type, long count, long offset) {
        int at = mapOff + 4 + index * 12;
        dex[at] = (byte) type;
        dex[at + 1] = (byte) (type >>> 8);
        u32(dex, at + 4, count);
        u32(dex, at + 8, offset);
    }

    private static byte[] dex(String... descriptors) {
        int count = descriptors.length;
        int stringOff = 112;
        int typeOff = stringOff + 4 * count;
        int classOff = typeOff + 4 * count;
        int mapOff = classOff + 32 * count;
        int firstText = mapOff + 68;
        byte[] bytes = new byte[firstText + count * 320 + 48];
        bytes[0] = 'd'; bytes[1] = 'e'; bytes[2] = 'x';
        bytes[3] = 10; bytes[4] = '0'; bytes[5] = '3'; bytes[6] = '9';
        u32(bytes, 32, bytes.length);
        u32(bytes, 36, 112);
        u32(bytes, 40, 0x12345678L);
        u32(bytes, 52, mapOff);
        u32(bytes, 56, count); u32(bytes, 60, stringOff);
        u32(bytes, 64, count); u32(bytes, 68, typeOff);
        u32(bytes, 96, count); u32(bytes, 100, classOff);
        u32(bytes, 104, bytes.length - mapOff);
        u32(bytes, 108, mapOff);
        u32(bytes, mapOff, 5);
        mapItem(bytes, mapOff, 0, 0, 1, 0);
        mapItem(bytes, mapOff, 1, 1, count, stringOff);
        mapItem(bytes, mapOff, 2, 2, count, typeOff);
        mapItem(bytes, mapOff, 3, 6, count, classOff);
        mapItem(bytes, mapOff, 4, 0x1000, 1, mapOff);
        for (int i = 0; i < count; i++) {
            int at = classOff + 32 * i;
            u32(bytes, at, i);
            u32(bytes, at + 8, 0xffffffffL);
            u32(bytes, at + 16, 0xffffffffL);
            u32(bytes, typeOff + i * 4, i);
            int strAt = firstText + 320 * i;
            u32(bytes, stringOff + i * 4, strAt);
            // Fixture only uses ASCII and two/three-byte BMP UTF-8 which
            // coincide with DEX MUTF-8 when U+0000 isn't present.
            byte[] utf = descriptors[i].getBytes(StandardCharsets.UTF_8);
            if (utf.length >= 300 || descriptors[i].length() >= 128)
                throw new IllegalArgumentException("Fixture too long");
            bytes[strAt] = (byte) descriptors[i].length(); // single-byte ULEB128
            System.arraycopy(utf, 0, bytes, strAt + 1, utf.length);
            bytes[strAt + 1 + utf.length] = 0;
        }
        return bytes;
    }

    private static DexClassNameProbe.Source source(byte[] input) {
        return () -> new ByteArrayInputStream(input);
    }

    private static void reject(byte[] bytes) throws Exception {
        try {
            DexClassNameProbe.inspect(source(bytes), bytes.length);
            fail("Tampered DEX descriptor must be rejected");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void resolvesClassNamesThroughBothTablesAndKeepsZipUntouched()
            throws Exception {
        byte[] bytes = dex("Lcom/example/Demo;", "Lcom/example/Second;");
        byte[] original = bytes.clone();
        DexClassNameProbe.Result result = DexClassNameProbe.inspect(source(bytes), bytes.length);
        assertEquals(2, result.declaredClasses);
        assertEquals(2, result.items.size());
        assertEquals("com.example.Demo", result.items.get(0).name);
        assertEquals("Lcom/example/Second;", result.items.get(1).descriptor);
        assertFalse(result.truncated);
        assertArrayEquals(original, bytes);
    }

    @Test public void unicodeMutf8InClassDescriptorsIsAccepted() throws Exception {
        byte[] bytes = dex("Lcom/Ônibus/Pará;", "Lbr/测试/路线;");
        DexClassNameProbe.Result report = DexClassNameProbe.inspect(source(bytes), bytes.length);
        assertEquals("com.Ônibus.Pará", report.items.get(0).name);
        assertEquals("br.测试.路线", report.items.get(1).name);
    }

    @Test public void onlySixNamesAreResolvedAndTruncationIsExplicit() throws Exception {
        String[] names = new String[8];
        for (int i = 0; i < names.length; i++) names[i] = "Lapp/Item" + i + ";";
        byte[] bytes = dex(names);
        DexClassNameProbe.Result result = DexClassNameProbe.inspect(source(bytes), bytes.length);
        assertEquals(8, result.declaredClasses);
        assertEquals(6, result.items.size());
        assertTrue(result.truncated);
        try {
            result.items.add(result.items.get(0));
            fail("Preview must be immutable");
        } catch (UnsupportedOperationException expected) {
            assertTrue(true);
        }
    }

    @Test public void rejectsForgedTypeOrStringIndices() throws Exception {
        byte[] bytes = dex("Lapp/First;");
        u32(bytes, 116, 1); // type_ids[0] at offset 116, string index >= count
        reject(bytes);
        bytes = dex("Lapp/First;");
        u32(bytes, 116, 0xffffffffL);
        reject(bytes);
        bytes = dex("Lapp/First;");
        u32(bytes, 112, bytes.length); // string_data_off at EOF
        reject(bytes);
        bytes = dex("Lapp/First;");
        u32(bytes, 112, 8); // string outside data region
        reject(bytes);
    }

    @Test public void rejectsMalformedMutf8LengthOrClassDescriptor() throws Exception {
        byte[] bytes = dex("Lapp/First;");
        int strAt = 112 + 4 + 4 + 32 + 68;
        bytes[strAt] = (byte) 0xff; // invalid huge ULEB128 or malformed
        reject(bytes);
        bytes = dex("Lapp/First;");
        bytes[strAt + 2] = (byte) 0xff; // illegal leading MUTF-8 byte
        reject(bytes);
        bytes = dex("Lapp/First;");
        bytes[strAt + 1] = (byte) 'X'; // not a class descriptor
        reject(bytes);
        bytes = dex("Lapp/First;");
        bytes[strAt + 5] = 0; // terminator early
        reject(bytes);
        bytes = dex("Lapp/First;");
        bytes[strAt + 1] = (byte) '['; // array descriptor not class
        reject(bytes);
    }

    @Test public void truncationAndInterruptedStreamsFailClosed() throws Exception {
        byte[] bytes = dex("Lapp/First;");
        try {
            DexClassNameProbe.inspect(() -> new ByteArrayInputStream(
                Arrays.copyOf(bytes, 40)), bytes.length);
            fail("Incomplete header must fail");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
        Thread.currentThread().interrupt();
        try {
            DexClassNameProbe.inspect(source(bytes), bytes.length);
            fail("Interrupt must stop reader");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(Thread.currentThread().isInterrupted());
        } finally { Thread.interrupted(); }
    }

    @Test public void scannerAddsRealNamePreviewWithoutTrustingMalformedDex()
            throws Exception {
        File apk = File.createTempFile("readroid_m34_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                out.putNextEntry(new ZipEntry("classes.dex"));
                out.write(dex("Lcom/negresco/Main;", "Lcom/negresco/Editor;"));
                out.closeEntry();
                out.putNextEntry(new ZipEntry("classes2.dex"));
                out.write(new byte[]{'x','y','z'});
                out.closeEntry();
            }
            try (ZipFile zip = new ZipFile(apk)) {
                JSONObject report = SecurityScanner.scan(zip);
                JSONArray names = report.getJSONArray("dexClassNamePreview");
                assertEquals(2, names.length());
                JSONObject valid = names.getJSONObject(0);
                assertEquals("class-names-preview", valid.getString("status"));
                assertEquals("com.negresco.Main",
                    valid.getJSONArray("resolvedClasses").getJSONObject(0).getString("name"));
                assertEquals("unreadable-class-names",
                    names.getJSONObject(1).getString("status"));
                assertFalse(report.getBoolean("dexClassNamePreviewTruncated"));
            }
        } finally { apk.delete(); }
    }
}
