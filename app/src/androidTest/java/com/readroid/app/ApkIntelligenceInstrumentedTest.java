package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Detection is strictly based on structural hints from synthetic fixtures. */
@RunWith(AndroidJUnit4.class)
public final class ApkIntelligenceInstrumentedTest {
    private static JSONObject report(String... names) throws Exception {
        JSONArray files = new JSONArray();
        for (String path : names)
            files.put(new JSONObject().put("path", path).put("category", "Outros"));
        return new JSONObject().put("explorer", new JSONObject().put("files", files));
    }

    @Test public void unityIndicatorsSuggestUnityButNotBinaryEditing() throws Exception {
        JSONObject p = ApkIntelligence.inspect(report(
            "lib/arm64-v8a/libunity.so", "assets/bin/Data/globalgamemanagers"));
        assertEquals("Unity", p.getString("platformHint"));
        assertEquals("indício estrutural", p.getString("confidence"));
        assertTrue(ApkIntelligence.describe(p).contains("Não edita assets Unity/Unreal"));
        assertTrue(p.getBoolean("localOnly"));
    }

    @Test public void unrealAndFlutterHaveDistinctIndicators() throws Exception {
        assertEquals("Unreal Engine", ApkIntelligence.inspect(
            report("lib/arm64-v8a/libUE4.so")).getString("platformHint"));
        assertEquals("Flutter", ApkIntelligence.inspect(
            report("assets/flutter_assets/AssetManifest.json")).getString("platformHint"));
    }

    @Test public void reactNativeAndOrdinaryAndroidAreDistinguished() throws Exception {
        assertEquals("React Native", ApkIntelligence.inspect(
            report("assets/index.android.bundle")).getString("platformHint"));
        JSONObject ordinary = ApkIntelligence.inspect(
            report("classes.dex", "AndroidManifest.xml"));
        assertEquals("Android/ZIP", ordinary.getString("platformHint"));
        assertEquals("não identificada", ordinary.getString("confidence"));
    }

    @Test public void mixedSignalsAreNotPresentedAsCertain() throws Exception {
        JSONObject p = ApkIntelligence.inspect(report("lib/x86/libunity.so",
            "lib/x86/libflutter.so"));
        assertEquals("Sinais mistos", p.getString("platformHint"));
        assertEquals("ambíguo", p.getString("confidence"));
        assertEquals(2, p.getJSONArray("evidence").length());
    }

    @Test public void noImportedCodeIsNeededToProfileAnApk() throws Exception {
        JSONObject p = ApkIntelligence.inspect(report("classes2.dex",
            "res/drawable/icon.png", "lib/arm64-v8a/libnative.so"));
        String description = ApkIntelligence.describe(p);
        assertTrue(description.contains("FERRAMENTAS DISPONÍVEIS AGORA"));
        assertTrue(description.contains("AINDA NÃO SUPORTADO"));
        assertTrue(description.contains("Nenhuma modificação automática"));
    }
}
