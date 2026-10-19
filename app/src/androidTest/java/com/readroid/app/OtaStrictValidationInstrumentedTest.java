package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.File;
import static org.junit.Assert.*;

/** Regression tests for strict OTA metadata and fail-closed direct downloads. */
@RunWith(AndroidJUnit4.class)
public final class OtaStrictValidationInstrumentedTest {
    private static final String HASH =
        "0000000000000000000000000000000000000000000000000000000000000000";

    private static JSONObject manifest() throws Exception {
        return new JSONObject().put("versionCode", 10)
            .put("versionName", "3.0.1")
            .put("channel", "beta")
            .put("downloadUrl", "https://example.invalid/release.apk")
            .put("sha256", HASH)
            .put("sizeBytes", 100L)
            .put("notes", "Teste local");
    }

    private static void assertRejected(JSONObject value) throws Exception {
        assertRejectedRaw(value.toString());
    }

    private static void assertRejectedRaw(String json) throws Exception {
        try {
            OtaRelease.parse(json);
            fail("Malformed OTA JSON must be rejected: " + json);
        } catch (IllegalArgumentException expected) {
            // A rejected manifest may never initiate a download.
        }
    }

    @Test public void rejectsCoercedVersionAndSizeNumbers() throws Exception {
        assertRejected(manifest().put("versionCode", "10"));
        assertRejected(manifest().put("versionCode", 10.5));
        // Construct the raw token: JSONObject.put(10.0) may serialize as "10".
        assertRejectedRaw(manifest().toString()
            .replace("\"versionCode\":10", "\"versionCode\":10.0"));
        assertRejected(manifest().put("sizeBytes", "100"));
        assertRejected(manifest().put("sizeBytes", 100.5));
        assertRejected(manifest().put("versionCode", (long) Integer.MAX_VALUE + 1));
    }

    @Test public void rejectsCoercedTextAndNonstandardHttpsPorts() throws Exception {
        assertRejected(manifest().put("versionName", 301));
        assertRejected(manifest().put("channel", true));
        assertRejected(manifest().put("notes", JSONObject.NULL));
        assertRejected(manifest().put("downloadUrl", "https://example.invalid:8443/release.apk"));
        // Explicit 443 remains valid; standard HTTPS port is not an exception.
        OtaRelease valid = OtaRelease.parse(manifest()
            .put("downloadUrl", "https://example.invalid:443/release.apk").toString());
        assertFalse(valid.hasVerifiedSignature());
    }

    @Test public void directDownloaderRejectsUnsignedManifestWithoutCacheWrites()
            throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File dir = context.getCacheDir();
        int before = countOtaFiles(dir);
        OtaRelease unsigned = OtaRelease.parse(manifest().toString());
        assertFalse(unsigned.hasVerifiedSignature());
        try {
            OtaApkDownloader.download(unsigned, dir);
            fail("Direct download must reject unsigned JSON before network access");
        } catch (SecurityException expected) {
            assertTrue(expected.getMessage().contains("assinatura"));
        }
        assertEquals("No temporary APK may be created by a rejected request",
            before, countOtaFiles(dir));
    }

    private static int countOtaFiles(File dir) {
        File[] files = dir.listFiles((parent, name) ->
            name.startsWith("negresco_ota_") && name.endsWith(".apk"));
        return files == null ? 0 : files.length;
    }
}
