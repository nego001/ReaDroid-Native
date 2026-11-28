package com.readroid.app;

import android.content.Context;
import android.content.Intent;
import android.content.UriPermission;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Process;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.InputStream;
import java.lang.reflect.Field;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.Assert.*;

/**
 * F1.28: real Android DocumentsUI / ContentResolver persisted permission.
 *
 * This opt-in test class runs ONLY via tests/f128_real_saf_grant.sh after
 * the normal instrumentation suite. A real debug APK fixture is placed in the
 * disposable emulator Downloads directory; no mock grant, synthetic result,
 * replacement signing, or user-owned document is involved.
 */
@RunWith(AndroidJUnit4.class)
public final class F128RealSafGrantInstrumentedTest {
    private static final String PREF = "f128_ci_saf_grant";
    private static final String URI_KEY = "document_uri";
    private static final String HASH_KEY = "accepted_sha256";
    private static final String PID_KEY = "original_process_pid";
    private static final String FIXTURE = "F128_saf_permission_probe.apk";
    private static final int READ = Intent.FLAG_GRANT_READ_URI_PERMISSION;
    private static final String SHA_CHARS = "0123456789abcdef";

    private static Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }

    private static SharedPreferences state() {
        return context().getSharedPreferences(PREF, Context.MODE_PRIVATE);
    }

    private static Set<String> persisted() {
        Set<String> result = new HashSet<>();
        for (UriPermission permission :
                context().getContentResolver().getPersistedUriPermissions()) {
            if (permission.isReadPermission())
                result.add(permission.getUri().toString());
        }
        return result;
    }

    private static Uri savedUri() {
        String value = state().getString(URI_KEY, null);
        assertNotNull("Saved real SAF fixture URI missing", value);
        Uri uri = Uri.parse(value);
        assertEquals("content", uri.getScheme());
        return uri;
    }

    private static String sha256(Uri uri) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = context().getContentResolver().openInputStream(uri)) {
            assertNotNull("OS failed to open persisted SAF content", input);
            byte[] buf = new byte[8192];
            for (int n; (n = input.read(buf)) != -1;) digest.update(buf, 0, n);
        }
        StringBuilder hash = new StringBuilder();
        for (byte value : digest.digest()) {
            hash.append(SHA_CHARS.charAt((value >>> 4) & 15))
                .append(SHA_CHARS.charAt(value & 15));
        }
        return hash.toString();
    }

    private static Object field(Object object, String name) throws Exception {
        Field f = object.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(object);
    }

    private static UiObject2 find(UiDevice device, String label) {
        return device.wait(Until.findObject(By.textContains(label)), 8000);
    }

    private static void chooseFixtureFromPicker(UiDevice device) {
        assertTrue("Android document picker did not appear",
            device.wait(Until.hasObject(By.pkg("com.google.android.documentsui")), 10000)
            || device.wait(Until.hasObject(By.pkg("com.android.documentsui")), 10000)
            || device.wait(Until.hasObject(By.text("Recent")), 5000)
            || device.wait(Until.hasObject(By.text("Browse")), 5000));

        UiObject2 fixture = find(device, "F128_saf_permission_probe");
        if (fixture == null) {
            UiObject2 downloads = device.findObject(By.text("Downloads"));
            if (downloads == null) {
                UiObject2 roots = device.findObject(By.desc("Show roots"));
                if (roots != null) roots.click();
                downloads = device.wait(Until.findObject(By.text("Downloads")), 8000);
            }
            assertNotNull("Downloads root unavailable in system DocumentsUI", downloads);
            downloads.click();
            fixture = find(device, "F128_saf_permission_probe");
        }
        assertNotNull("Disposable APK fixture not listed in system picker", fixture);
        fixture.click();
    }

    @Test public void f128ObtainPersistedGrantFromSystemPicker() throws Exception {
        assertNull("Fixture state must be fresh", state().getString(URI_KEY, null));
        Set<String> before = persisted();
        UiDevice device = UiDevice.getInstance(
            InstrumentationRegistry.getInstrumentation());

        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("*/*");
                activity.startActivityForResult(pick, 1);
            });
            chooseFixtureFromPicker(device);

            Uri chosen = null;
            String digest = null;
            for (int attempt = 0; attempt < 40; attempt++) {
                Set<String> now = persisted();
                now.removeAll(before);
                if (now.size() == 1) {
                    Uri candidate = Uri.parse(now.iterator().next());
                    final boolean[] committed = {false};
                    final String[] acceptedHash = {null};
                    scenario.onActivity(activity -> {
                        try {
                            Uri accepted = (Uri) field(activity, "selectedApkUri");
                            JSONObject report = (JSONObject) field(activity, "report");
                            committed[0] = candidate.equals(accepted);
                            acceptedHash[0] = report == null ? null :
                                report.optString("sha256", "");
                        } catch (Exception error) { throw new AssertionError(error); }
                    });
                    if (committed[0] && SavedProjectResume.validSha256(acceptedHash[0])) {
                        chosen = candidate;
                        digest = acceptedHash[0];
                        break;
                    }
                }
                Thread.sleep(250);
            }
            assertNotNull("No fully accepted APK with real persistable SAF grant", chosen);
            assertEquals(digest, sha256(chosen));
            assertTrue(P7ProjectHistory.hasPermission(context(), chosen));
            SavedProjectResume.Decision cold = SavedProjectResume.decide(
                chosen, null, false, false, digest,
                uri -> P7ProjectHistory.hasPermission(context(), uri));
            assertEquals(chosen, cold.reimport);
            assertEquals(digest, cold.expectedSha256);
            assertTrue("Could not persist test state across process death",
                state().edit().putString(URI_KEY, chosen.toString())
                    .putString(HASH_KEY, digest).putInt(PID_KEY, Process.myPid()).commit());
        }
    }

    @Test public void f128AfterColdStartRevokeRealPersistedGrant() throws Exception {
        Uri uri = savedUri();
        String hash = state().getString(HASH_KEY, null);
        assertTrue(SavedProjectResume.validSha256(hash));
        assertNotEquals("Process must be new after external force-stop",
            state().getInt(PID_KEY, -1), Process.myPid());
        assertTrue("OS did not retain the SAF permission across process restart",
            persisted().contains(uri.toString()));
        assertTrue(P7ProjectHistory.hasPermission(context(), uri));
        assertEquals(hash, sha256(uri));
        SavedProjectResume.Decision allowed = SavedProjectResume.decide(
            uri, null, false, false, hash,
            candidate -> P7ProjectHistory.hasPermission(context(), candidate));
        assertEquals(uri, allowed.reimport);

        // Real Android API revocation (not a fake ReadGrant checker).
        context().getContentResolver().releasePersistableUriPermission(uri, READ);
        assertFalse("Real persisted URI grant survived revocation",
            persisted().contains(uri.toString()));
        assertFalse(P7ProjectHistory.hasPermission(context(), uri));
        SavedProjectResume.Decision denied = SavedProjectResume.decide(
            uri, null, false, false, hash,
            candidate -> P7ProjectHistory.hasPermission(context(), candidate));
        assertNull(denied.reimport);
        assertNull(denied.acceptedReference);
        assertTrue(denied.requiresReselection);
        assertTrue(state().edit().putInt(PID_KEY, Process.myPid()).commit());
    }

    @Test public void f128NextProcessRejectsRevokedGrant() throws Exception {
        Uri uri = savedUri();
        String hash = state().getString(HASH_KEY, null);
        assertNotEquals("Cold restart must create a different app process",
            state().getInt(PID_KEY, -1), Process.myPid());
        assertFalse(persisted().contains(uri.toString()));
        assertFalse(P7ProjectHistory.hasPermission(context(), uri));
        SavedProjectResume.Decision denied = SavedProjectResume.decide(
            uri, null, false, false, hash,
            candidate -> P7ProjectHistory.hasPermission(context(), candidate));
        assertNull(denied.reimport);
        assertTrue(denied.requiresReselection);
        assertTrue("Test-only metadata cleanup failed", state().edit().clear().commit());
    }
}
