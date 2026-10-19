package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.util.Arrays;

import static org.junit.Assert.*;

/** OTA is opt-in and must remain inert without pinned endpoint and trust key. */
@RunWith(AndroidJUnit4.class)
public final class OtaDisabledInstrumentedTest {
    private static final String DIGEST = "00000000000000000000000000000000"
        + "00000000000000000000000000000000";

    private OtaRelease untrustedRelease(String channel) throws Exception {
        JSONObject value = new JSONObject()
            .put("versionCode", 999999)
            .put("versionName", "999.0.0")
            .put("channel", channel)
            .put("downloadUrl", "https://example.invalid/untrusted.apk")
            .put("sha256", DIGEST)
            .put("sizeBytes", 1024)
            .put("notes", "Not a signed release");
        return OtaRelease.parse(value.toString());
    }

    @Test public void stableAndBetaAreUnconfiguredAndCannotCheck() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        for (String channel : new String[]{"stable", "beta"}) {
            assertFalse("This test must be updated if trust pins are configured",
                OtaConfig.isConfigured(channel));
            try {
                OtaUpdatePipeline.check(context, "https://example.invalid/manifest.json",
                    "forged-key", channel);
                fail("An unconfigured OTA channel must reject check requests");
            } catch (SecurityException expected) {
                assertTrue(expected.getMessage().contains("não configurada")
                    || expected.getMessage().contains("não confiável"));
            }
        }
    }

    @Test public void directDownloadIsBlockedBeforeCreatingCacheOrStartingNetwork()
            throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences("MainActivity", Context.MODE_PRIVATE);
        String priorChannel = prefs.getString("ota_channel", "stable");
        try {
            for (String channel : new String[]{"stable", "beta"}) {
                assertTrue(prefs.edit().putString("ota_channel", channel).commit());
                int before = countDownloads(context.getCacheDir());
                try {
                    OtaUpdatePipeline.downloadAndVerify(context, untrustedRelease(channel));
                    fail("Unsigned OTA metadata must not trigger a download");
                } catch (SecurityException expected) {
                    assertTrue(expected.getMessage().contains("não configurada"));
                }
                assertEquals("Rejected OTA must not create temporary files",
                    before, countDownloads(context.getCacheDir()));
            }
        } finally {
            assertTrue(prefs.edit().putString("ota_channel", priorChannel).commit());
        }
    }

    private static int countDownloads(File dir) {
        File[] files = dir.listFiles((parent, name) ->
            name.startsWith("negresco_ota_") && name.endsWith(".apk"));
        return files == null ? 0 : files.length;
    }
}
