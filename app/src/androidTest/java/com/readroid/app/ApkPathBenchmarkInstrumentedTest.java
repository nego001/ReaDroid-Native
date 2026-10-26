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
 * M2.6 paired observational benchmark, not a speed or memory acceptance gate.
 * Compare baseline String retention with M2.5's fingerprint retention on the
 * same emulator and same deterministic workload, alternating ABBA order.
 * Only aggregate synthetic counters are emitted, never ZIP path content.
 */
@RunWith(AndroidJUnit4.class)
public final class ApkPathBenchmarkInstrumentedTest {
    private static final int PATHS = 8192;
    private static final String TAG = "M2Fingerprint";
    private static volatile Object retained;

    private static String prefix() {
        StringBuilder out = new StringBuilder("assets/bench/");
        while (out.length() < 770) out.append('b');
        return out.toString();
    }

    private static void gc() {
        System.gc();
        System.runFinalization();
        System.gc();
    }

    private static long heap() {
        Runtime runtime = Runtime.getRuntime();
        return runtime.totalMemory() - runtime.freeMemory();
    }

    private static void warmUp(String prefix) throws Exception {
        Set<String> originals = new HashSet<>();
        ApkPathFingerprintSet compact = new ApkPathFingerprintSet();
        for (int i = 0; i < 256; i++) {
            String path = prefix + i + ".dat";
            ApkDiskIndex.validatePath(path);
            assertTrue(originals.add(path));
            compact.requireUnique(path);
        }
        assertEquals(256, originals.size());
        assertEquals(256, compact.size());
    }

    private static JSONObject sample(boolean useFingerprint, String prefix,
            String phase) throws Exception {
        retained = null;
        gc();
        long baselineHeap = heap();
        long startWall = SystemClock.elapsedRealtime();
        long startCpu = Process.getElapsedCpuTime();
        int count;
        if (useFingerprint) {
            ApkPathFingerprintSet fingerprints = new ApkPathFingerprintSet();
            for (int i = 0; i < PATHS; i++) {
                String path = prefix + i + ".dat";
                ApkDiskIndex.validatePath(path);
                fingerprints.requireUnique(path);
            }
            count = fingerprints.size();
            retained = fingerprints;
        } else {
            Set<String> strings = new HashSet<>();
            for (int i = 0; i < PATHS; i++) {
                String path = prefix + i + ".dat";
                ApkDiskIndex.validatePath(path);
                assertTrue(strings.add(path));
            }
            count = strings.size();
            retained = strings;
        }
        long wallMs = Math.max(0, SystemClock.elapsedRealtime() - startWall);
        long cpuMs = Math.max(0, Process.getElapsedCpuTime() - startCpu);
        assertEquals(PATHS, count);
        gc(); // Observational retained heap after garbage collection.
        long heapWithSet = heap();
        JSONObject result = new JSONObject();
        result.put("phase", phase);
        result.put("kind", useFingerprint ? "fingerprint128" : "stringSet");
        result.put("paths", count);
        result.put("wallMs", wallMs);
        result.put("processCpuMs", cpuMs);
        result.put("heapBeforeBytes", baselineHeap);
        result.put("heapRetainedBytes", heapWithSet);
        result.put("heapDeltaBytes", heapWithSet - baselineHeap);
        result.put("processPssKib", Debug.getPss());
        retained = null;
        return result;
    }

    @Test public void pairedLongPathProfileRetainsAllUniquenessProtections()
            throws Exception {
        String common = prefix();
        warmUp(common);
        JSONArray samples = new JSONArray();
        samples.put(sample(false, common, "A1"));
        samples.put(sample(true, common, "B1"));
        samples.put(sample(true, common, "B2"));
        samples.put(sample(false, common, "A2"));
        JSONObject result = new JSONObject();
        result.put("schema", "m2_path_fingerprint_abba_v1");
        result.put("synthetic", true);
        result.put("deviceApi", android.os.Build.VERSION.SDK_INT);
        result.put("pathsPerSample", PATHS);
        result.put("pathPrefixChars", common.length());
        result.put("samples", samples);
        result.put("result", "PASS");
        // Full evidence is emitted while instrumentation still has app access.
        Log.i(TAG, "RESULT_JSON:" + result.toString());
    }
}
