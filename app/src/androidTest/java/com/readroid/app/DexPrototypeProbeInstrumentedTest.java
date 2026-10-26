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
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/**
 * M3.6 synthetic DEX metadata with coherent method_ids, proto_ids,
 * type_ids, string_ids and parameter type_list. Not executable bytecode.
 */
@RunWith(AndroidJUnit4.class)
public final class DexPrototypeProbeInstrumentedTest {
    private static final int STRING_OFF = 112;
    private static final int MAP_OFF = 512;
    private static final int PARAMETERS_OFF = 608;
    private static final int TEXT_OFF = 896;
    private static final int SLOT = 160;

    private static void u32(byte[] value, int offset, long number) {
        for (int i = 0; i < 4; i++) value[offset + i] = (byte) (number >>> (8 * i));
    }

    private static void u16(byte[] value, int offset, int number) {
        value[offset] = (byte) number;
        value[offset + 1] = (byte) (number >>> 8);
    }

    private static void mapEntry(byte[] bytes, int index, int type,
            long count, long offset) {
        int at = MAP_OFF + 4 + index * 12;
        u16(bytes, at, type);
        u32(bytes, at + 4, count);
        u32(bytes, at + 8, offset);
    }

    private static final class Fixture {
        final byte[] bytes;
        final int typeOffset;
        final int protoOffset;
        final int methodOffset;
        Fixture(byte[] bytes, int typeOffset, int protoOffset, int methodOffset) {
            this.bytes = bytes;
            this.typeOffset = typeOffset;
            this.protoOffset = protoOffset;
            this.methodOffset = methodOffset;
        }
    }

    private static Fixture fixture(int parameterCount, String... methodNames) {
        if (parameterCount < 0 || parameterCount > 2 || methodNames.length < 1
                || methodNames.length > 10)
            throw new IllegalArgumentException("Invalid synthetic fixture");
        String shorty = parameterCount == 0 ? "V"
            : parameterCount == 1 ? "VI" : "VIL";
        String[] names = new String[5 + methodNames.length];
        names[0] = "Lapp/Runner;";
        names[1] = shorty;
        names[2] = "V";
        names[3] = "I";
        names[4] = "Ljava/lang/String;";
        System.arraycopy(methodNames, 0, names, 5, methodNames.length);
        int typeOffset = STRING_OFF + names.length * 4;
        int protoOffset = typeOffset + 4 * 4;
        int methodOffset = protoOffset + 12;
        byte[] bytes = new byte[TEXT_OFF + SLOT * names.length + 32];

        bytes[0]='d'; bytes[1]='e'; bytes[2]='x'; bytes[3]=10;
        bytes[4]='0'; bytes[5]='3'; bytes[6]='9';
        u32(bytes, 32, bytes.length);
        u32(bytes, 36, 112);
        u32(bytes, 40, 0x12345678L);
        u32(bytes, 52, MAP_OFF);
        u32(bytes, 56, names.length); u32(bytes, 60, STRING_OFF);
        u32(bytes, 64, 4); u32(bytes, 68, typeOffset);
        u32(bytes, 72, 1); u32(bytes, 76, protoOffset);
        u32(bytes, 88, methodNames.length); u32(bytes, 92, methodOffset);
        u32(bytes, 104, bytes.length - MAP_OFF);
        u32(bytes, 108, MAP_OFF);

        u32(bytes, typeOffset, 0);  // declaring type
        u32(bytes, typeOffset + 4, 2); // V return
        u32(bytes, typeOffset + 8, 3); // I parameter
        u32(bytes, typeOffset + 12, 4); // Ljava/lang/String;
        u32(bytes, protoOffset, 1);  // shorty_idx
        u32(bytes, protoOffset + 4, 1); // return_type_idx = V
        u32(bytes, protoOffset + 8, parameterCount == 0 ? 0 : PARAMETERS_OFF);

        if (parameterCount != 0) {
            u32(bytes, PARAMETERS_OFF, parameterCount);
            u16(bytes, PARAMETERS_OFF + 4, 2);
            if (parameterCount == 2) u16(bytes, PARAMETERS_OFF + 6, 3);
        }
        for (int i = 0; i < methodNames.length; i++) {
            int at = methodOffset + 8 * i;
            u16(bytes, at, 0);
            u16(bytes, at + 2, 0);
            u32(bytes, at + 4, i + 5);
        }
        u32(bytes, MAP_OFF, 6);
        mapEntry(bytes, 0, 0, 1, 0);
        mapEntry(bytes, 1, 1, names.length, STRING_OFF);
        mapEntry(bytes, 2, 2, 4, typeOffset);
        mapEntry(bytes, 3, 3, 1, protoOffset);
        mapEntry(bytes, 4, 5, methodNames.length, methodOffset);
        mapEntry(bytes, 5, 0x1000, 1, MAP_OFF);

        for (int i = 0; i < names.length; i++) {
            int at = TEXT_OFF + i * SLOT;
            byte[] utf8 = names[i].getBytes(java.nio.charset.StandardCharsets.UTF_8);
            if (names[i].length() > 120 || utf8.length() >= SLOT - 4)
                throw new IllegalArgumentException("Synthetic string too long");
            u32(bytes, STRING_OFF + i * 4, at);
            bytes[at] = (byte) names[i].length(); // one-byte ULEB128
            System.arraycopy(utf8, 0, bytes, at + 1, utf8.length);
            bytes[at + utf8.length + 1] = 0;
        }
        return new Fixture(bytes, typeOffset, protoOffset, methodOffset);
    }

    private static DexPrototypeProbe.Result inspect(Fixture source) throws IOException {
        return DexPrototypeProbe.inspect(
            () -> new ByteArrayInputStream(source.bytes), source.bytes.length);
    }

    private static void rejected(Fixture source) throws Exception {
        try {
            inspect(source);
            fail("Invalid DEX proto must be rejected");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void resolvesReturnAndIntParameterIntoFullSignature()
            throws Exception {
        Fixture f = fixture(1, "executar");
        byte[] original = f.bytes.clone();
        DexPrototypeProbe.Result result = inspect(f);
        assertEquals(1L, result.totalMethodIds);
        assertFalse(result.truncated);
        assertEquals(1, result.signatures.size());
        DexPrototypeProbe.MethodSignature item = result.signatures.get(0);
        assertEquals("executar", item.methodName);
        assertEquals("V", item.returnType);
        assertEquals("I", item.parameterTypes.get(0));
        assertEquals("(I)V", item.descriptor);
        assertArrayEquals(original, f.bytes);
    }

    @Test public void supportsNoParametersObjectParametersAndFourItemCap()
            throws Exception {
        DexPrototypeProbe.Result none = inspect(fixture(0, "abrir"));
        assertEquals("()V", none.signatures.get(0).descriptor);
        DexPrototypeProbe.Result two = inspect(fixture(2, "abrir"));
        assertEquals("(ILjava/lang/String;)V", two.signatures.get(0).descriptor);
        // Arrays become 'L' in the shorty, even when the full type is [I.
        Fixture array = fixture(1, "abrir");
        int arrayString = TEXT_OFF + SLOT * 4;
        array.bytes[arrayString] = 2; // UTF-16 length
        array.bytes[arrayString + 1] = '[';
        array.bytes[arrayString + 2] = 'I';
        array.bytes[arrayString + 3] = 0;
        array.bytes[TEXT_OFF + SLOT + 2] = 'L'; // shorty V(L)
        u16(array.bytes, PARAMETERS_OFF + 4, 3);
        assertEquals("([I)V", inspect(array).signatures.get(0).descriptor);
        Fixture five = fixture(1, "a", "b", "c", "d", "e");
        DexPrototypeProbe.Result sampled = inspect(five);
        assertEquals(5L, sampled.totalMethodIds);
        assertEquals(4, sampled.signatures.size());
        assertTrue(sampled.truncated);
        try {
            sampled.signatures.add(sampled.signatures.get(0));
            fail("Method signatures should not be mutable");
        } catch (UnsupportedOperationException expected) {
            assertTrue(true);
        }
    }

    @Test public void rejectsForgedProtoIndicesAndInvalidReturnTypes()
            throws Exception {
        Fixture f = fixture(1, "abrir");
        u32(f.bytes, f.protoOffset + 4, 4); rejected(f);
        f = fixture(1, "abrir");
        u32(f.bytes, f.protoOffset, 99); rejected(f);
        f = fixture(1, "abrir");
        u32(f.bytes, f.typeOffset + 4, 99); rejected(f);
    }

    @Test public void rejectsShortyMismatchAndInvalidTypeDescriptors()
            throws Exception {
        Fixture f = fixture(1, "abrir");
        // Change VI to VV: param type is still I, so the shorty contradicts it.
        f.bytes[TEXT_OFF + SLOT + 2] = (byte) 'V';
        rejected(f);
        f = fixture(1, "abrir");
        // A parameter with the void descriptor is not legal.
        u16(f.bytes, PARAMETERS_OFF + 4, 1);
        rejected(f);
        f = fixture(1, "abrir");
        // A string descriptor containing '.' is not valid for object type.
        int nameAt = TEXT_OFF + SLOT * 4 + 1;
        f.bytes[nameAt + 5] = (byte) '.';
        u16(f.bytes, PARAMETERS_OFF + 4, 3);
        rejected(f);
    }

    @Test public void rejectsOversizedOrMisalignedParameterLists()
            throws Exception {
        Fixture f = fixture(1, "abrir");
        u32(f.bytes, PARAMETERS_OFF, 9); rejected(f);
        f = fixture(1, "abrir");
        u32(f.bytes, f.protoOffset + 8, PARAMETERS_OFF + 1); rejected(f);
        f = fixture(1, "abrir");
        u32(f.bytes, f.protoOffset + 8, f.bytes.length); rejected(f);
        f = fixture(1, "abrir");
        u16(f.bytes, PARAMETERS_OFF + 4, 4); rejected(f);
    }

    @Test public void rejectsBadMutf8AndTruncatedStreams() throws Exception {
        Fixture f = fixture(1, "abrir");
        f.bytes[TEXT_OFF + SLOT + 1] = (byte) 0xff; rejected(f);
        f = fixture(1, "abrir");
        try {
            DexPrototypeProbe.inspect(
                () -> new ByteArrayInputStream(new byte[]{'d', 'e', 'x'}),
                f.bytes.length);
            fail("Truncated input should be rejected");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
    }

    @Test public void cancellationKeepsInterruptFlagAndDoesNotReturnResult()
            throws Exception {
        Fixture f = fixture(1, "abrir");
        Thread.currentThread().interrupt();
        try {
            inspect(f);
            fail("Cancelled DEX stream should stop");
        } catch (java.io.InterruptedIOException expected) {
            assertTrue(Thread.currentThread().isInterrupted());
        } finally {
            Thread.interrupted();
        }
    }

    @Test public void scannerShowsSignaturesButNotClaimedImplementations()
            throws Exception {
        File apk = File.createTempFile("readroid_m36_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                zip.putNextEntry(new ZipEntry("classes.dex"));
                zip.write(fixture(2, "analisar").bytes);
                zip.closeEntry();
                zip.putNextEntry(new ZipEntry("classes2.dex"));
                zip.write(new byte[]{'X', 'Y', 'Z'});
                zip.closeEntry();
            }
            try (ZipFile zip = new ZipFile(apk)) {
                JSONObject report = SecurityScanner.scan(zip);
                JSONArray previews = report.getJSONArray("dexPrototypePreview");
                assertEquals(2, previews.length());
                JSONObject good = previews.getJSONObject(0);
                assertEquals("prototype-signatures-preview", good.getString("status"));
                assertEquals("(ILjava/lang/String;)V", good
                    .getJSONArray("methodSignatures").getJSONObject(0)
                    .getString("signature"));
                assertEquals("unreadable-prototypes",
                    previews.getJSONObject(1).getString("status"));
                assertFalse(report.getBoolean("dexPrototypePreviewTruncated"));
                assertTrue(report.getString("limitations").contains("externos"));
            }
        } finally {
            apk.delete();
        }
    }
}
