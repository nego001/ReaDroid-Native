package com.readroid.app;

import android.os.Debug;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Random;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/**
 * M2.4 observational capacity profile. Timings, Java heap and process PSS
 * are recorded, NOT asserted against an emulator-dependent speed threshold.
 * Only structural, integrity and 120-item memory-budget invariants are gates.
 * APKs are generated locally and deleted; published evidence is metrics JSON.
 */
@RunWith(AndroidJUnit4.class)
public final class ApkCapacityProfileInstrumentedTest {
    private static final int FILE_COUNT = 2500;
    private static final int DATA_BYTES = 4096;
    private static final String TAG = "M2Capacity";

    private static JSONObject measure(String stage, long startWall, long startCpu)
            throws Exception {
        long wallMs = Math.max(0L, SystemClock.elapsedRealtime() - startWall);
        long cpuMs = Math.max(0L, Process.getElapsedCpuTime() - startCpu);
        Runtime runtime = Runtime.getRuntime();
        JSONObject metric = new JSONObject();
        metric.put("stage", stage);
        metric.put("wallMs", wallMs);
        metric.put("processCpuMs", cpuMs);
        metric.put("javaHeapUsedBytes", runtime.totalMemory() - runtime.freeMemory());
        metric.put("nativeHeapAllocatedBytes", Debug.getNativeHeapAllocatedSize());
        metric.put("processPssKib", Debug.getPss());
        Log.i(TAG, metric.toString());
        return metric;
    }

    @Test public void measuresManyPathsWithoutGrowingJsonOrLosingIndexTail()
            throws Exception {
        File cache = InstrumentationRegistry.getInstrumentation()
            .getTargetContext().getCacheDir();
        File apk = File.createTempFile("readroid_capacity_", ".apk", cache);
        File index = new File(apk.getAbsolutePath() + ".idx.db");
        // A single small JSON-only evidence file: never export fixture APKs.
        File evidence = new File(cache, "m2_capacity_metrics.json");
        JSONObject metrics = new JSONObject();
        try {
            long wall = SystemClock.elapsedRealtime();
            long cpu = Process.getElapsedCpuTime();
            Random random = new Random(0x4D324CL);
            byte[] data = new byte[DATA_BYTES];
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                zip.putNextEntry(new ZipEntry("AndroidManifest.xml"));
                zip.write(new byte[]{3, 0, 8, 0});
                zip.closeEntry();
                zip.putNextEntry(new ZipEntry("classes.dex"));
                zip.write(new byte[]{100, 101, 120, 10, 0, 0, 0});
                zip.closeEntry();
                zip.putNextEntry(new ZipEntry("assets/empty/"));
                zip.closeEntry();
                for (int i = 0; i < FILE_COUNT; i++) {
                    random.nextBytes(data);
                    String path = String.format(Locale.ROOT,
                        "assets/capacity/tracks/track_%04d.bin", i);
                    zip.putNextEntry(new ZipEntry(path));
                    zip.write(data);
                    zip.closeEntry();
                }
            }
            metrics.put("fixture", new JSONObject()
                .put("synthetic", true)
                .put("contentBytes", (long) FILE_COUNT * DATA_BYTES + 11)
                .put("archiveBytes", apk.length())
                .put("fileCount", FILE_COUNT + 2)
                .put("entryCount", FILE_COUNT + 3)
                .put("deviceApi", android.os.Build.VERSION.SDK_INT));
            metrics.put("fixtureGeneration", measure("fixtureGeneration", wall, cpu));
            final String before = ApkIntegrity.sha256(apk);
            assertEquals(64, before.length());

            wall = SystemClock.elapsedRealtime();
            cpu = Process.getElapsedCpuTime();
            ApkArchiveSafety.Stats admission = ApkArchiveSafety.verify(apk);
            metrics.put("zipAdmission", measure("zipAdmission", wall, cpu));
            assertEquals(FILE_COUNT + 3, admission.entries);
            assertEquals(FILE_COUNT + 2, admission.files);
            assertEquals((long) FILE_COUNT * DATA_BYTES + 11, admission.inflatedBytes);

            wall = SystemClock.elapsedRealtime();
            cpu = Process.getElapsedCpuTime();
            JSONObject summary = ApkExplorer.inspectVerified(apk);
            metrics.put("boundedPreview", measure("boundedPreview", wall, cpu));
            assertEquals(FILE_COUNT + 2, summary.getInt("fileCount"));
            assertEquals(120, summary.getJSONArray("files").length());
            assertTrue(summary.getBoolean("previewTruncated"));

            wall = SystemClock.elapsedRealtime();
            cpu = Process.getElapsedCpuTime();
            ApkDiskIndex.Stats built = ApkDiskIndex.build(apk, index);
            metrics.put("sqliteIndexBuild", measure("sqliteIndexBuild", wall, cpu));
            assertEquals(FILE_COUNT + 2, built.files);
            assertTrue(built.databaseBytes <= 128L * 1024 * 1024);
            assertTrue(ApkDiskIndex.containsDirectory(apk, index, "assets/empty/"));

            wall = SystemClock.elapsedRealtime();
            cpu = Process.getElapsedCpuTime();
            ApkDiskIndex.Page tail = ApkDiskIndex.page(apk, index, "",
                "track_2499.bin", "Todos", 0, 120);
            metrics.put("sqliteTailSearch", measure("sqliteTailSearch", wall, cpu));
            assertEquals(1, tail.totalMatches);
            assertEquals("assets/capacity/tracks/track_2499.bin",
                tail.items.get(0).path);

            wall = SystemClock.elapsedRealtime();
            cpu = Process.getElapsedCpuTime();
            try (ZipFile zip = new ZipFile(apk)) {
                JSONObject security = SecurityScanner.scan(zip);
                assertEquals(FILE_COUNT + 3, security.getInt("entries"));
                assertEquals(120, security.getJSONArray("fileExplorerPreview").length());
            }
            metrics.put("securityMetadata", measure("securityMetadata", wall, cpu));
            assertEquals("Original APK must remain byte-identical",
                before, ApkIntegrity.sha256(apk));
            metrics.put("result", "PASS");
            // connectedDebugAndroidTest can uninstall its target app after tests.
            // Emit only small, synthetic metrics to logcat so CI can collect
            // evidence without run-as access after instrumentation teardown.
            Log.i(TAG, "RESULT_JSON:" + metrics.toString());
            try (FileOutputStream out = new FileOutputStream(evidence)) {
                out.write(metrics.toString(2).getBytes(StandardCharsets.UTF_8));
            }
        } finally {
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }
}
