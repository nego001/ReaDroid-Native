package com.readroid.app;

import android.os.Debug;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.HashSet;
import java.util.Set;

import static org.junit.Assert.*;

/**
 * M2.8: three paired ABBA profiles for short, medium and long ZIP paths.
 * Observational CPU/retained-Java-heap data, no time-based CI assertions.
 * Each profile emits a separate small synthetic JSON line for logcat limits.
 */
@RunWith(AndroidJUnit4.class)
public final class ApkPathLengthProfileInstrumentedTest {
    private static final String TAG = "M2PathLength";
    private static final int NAMES = 4096;
    private static final int[] PATH_LENGTHS = {32, 128, 768};
    private static volatile Object held;

    private static String repeat(char ch, int n) {
        StringBuilder builder = new StringBuilder(n);
        for (int i = 0; i < n; i++) builder.append(ch);
        return builder.toString();
    }

    /** Path length is exact: assets/p/ + pad + /file_0000.txt. */
    private static String prefix(int targetLength) {
        String suffix = "/file_0000.txt";
        String fixed = "assets/p/";
        return fixed + repeat('x', targetLength - fixed.length() - suffix.length())
            + "/file_";
    }

    private static String path(String prefix, int index) {
        // Avoid format/locale allocations dominating the CPU comparison.
        char[] digits = new char[4];
        for (int p = 3; p >= 0; p--) {
            digits[p] = (char) ('0' + index % 10);
            index /= 10;
        }
        return prefix + new String(digits) + ".txt";
    }

    private static void collect() {
        System.gc();
        System.runFinalization();
        System.gc();
    }

    private static long heapBytes() {
        Runtime runtime = Runtime.getRuntime();
        return runtime.totalMemory() - runtime.freeMemory();
    }

    private static JSONObject trial(boolean fingerprint, String prefix,
            String phase, int length) throws Exception {
        held = null;
        collect();
        long heapBefore = heapBytes();
        long startCpu = Process.getElapsedCpuTime();
        long startWall = SystemClock.elapsedRealtime();
        int actual;
        if (fingerprint) {
            ApkPathFingerprintSet set = new ApkPathFingerprintSet();
            for (int i = 0; i < NAMES; i++) {
                String value = path(prefix, i);
                assertEquals(length, value.length());
                ApkDiskIndex.validatePath(value);
                set.requireUnique(value);
            }
            actual = set.size();
            held = set;
        } else {
            Set<String> set = new HashSet<>();
            for (int i = 0; i < NAMES; i++) {
                String value = path(prefix, i);
                assertEquals(length, value.length());
                ApkDiskIndex.validatePath(value);
                assertTrue(set.add(value));
            }
            actual = set.size();
            held = set;
        }
        long cpuMs = Math.max(0, Process.getElapsedCpuTime() - startCpu);
        long wallMs = Math.max(0, SystemClock.elapsedRealtime() - startWall);
        assertEquals(NAMES, actual);
        collect();
        long heapAfter = heapBytes();
        JSONObject result = new JSONObject();
        result.put("phase", phase);
        result.put("kind", fingerprint ? "fingerprint128" : "stringSet");
        result.put("paths", actual);
        result.put("cpuMs", cpuMs);
        result.put("wallMs", wallMs);
        result.put("heapDeltaBytes", heapAfter - heapBefore);
        result.put("pssKib", Debug.getPss());
        held = null;
        return result;
    }

    @Test public void threePathLengthProfilesProducePairedSyntheticEvidence()
            throws Exception {
        for (int length : PATH_LENGTHS) {
            String common = prefix(length);
            assertEquals(length, path(common, 4095).length());
            JSONArray pairs = new JSONArray();
            pairs.put(trial(false, common, "A1", length));
            pairs.put(trial(true, common, "B1", length));
            pairs.put(trial(true, common, "B2", length));
            pairs.put(trial(false, common, "A2", length));
            JSONObject report = new JSONObject();
            report.put("schema", "m2_path_length_abba_v1");
            report.put("synthetic", true);
            report.put("deviceApi", android.os.Build.VERSION.SDK_INT);
            report.put("pathChars", length);
            report.put("pathsPerSample", NAMES);
            report.put("samples", pairs);
            report.put("result", "PASS");
            // Three short log lines avoid Android logcat per-line truncation.
            Log.i(TAG, "RESULT_JSON:" + report.toString());
        }
    }
}
