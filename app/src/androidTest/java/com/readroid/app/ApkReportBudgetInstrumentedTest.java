package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** M2.3: bounded metadata, complete SQLite navigation and exhaustive signals. */
@RunWith(AndroidJUnit4.class)
public final class ApkReportBudgetInstrumentedTest {
    private File archive() throws IOException {
        return File.createTempFile("readroid_m23_", ".apk",
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
    }

    private static void add(ZipOutputStream out, String name) throws IOException {
        out.putNextEntry(new ZipEntry(name));
        out.write(new byte[]{42});
        out.closeEntry();
    }

    @Test public void longArchiveKeepsExactCountsAndTailEngineHints()
            throws Exception {
        File apk = archive();
        File index = new File(apk.getAbsolutePath() + ".idx.db");
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                add(out, "AndroidManifest.xml");
                add(out, "classes.dex");
                for (int i = 0; i < 240; i++)
                    add(out, String.format(Locale.ROOT, "assets/item_%03d.txt", i));
                // Unity/Flutter detection must not depend on the 120-path JSON preview.
                add(out, "assets/flutter_assets/AssetManifest.json");
            }
            JSONObject explorer = ApkExplorer.inspect(apk);
            assertEquals(243, explorer.getInt("fileCount"));
            assertEquals(243, explorer.getInt("entryCount"));
            assertEquals(120, explorer.getJSONArray("files").length());
            assertEquals(120, explorer.getInt("previewCount"));
            assertTrue(explorer.getBoolean("previewTruncated"));
            assertEquals(243, explorer.getJSONArray("files").length()
                + (explorer.getInt("fileCount") - explorer.getInt("previewCount")));
            JSONObject report = new JSONObject().put("explorer", explorer);
            assertEquals("Flutter", ApkIntelligence.inspect(report)
                .getString("platformHint"));
            assertEquals("indício estrutural", ApkIntelligence.inspect(report)
                .getString("confidence"));

            ApkDiskIndex.Stats stats = ApkDiskIndex.build(apk, index);
            assertEquals(243, stats.files);
            ApkDiskIndex.Page tail = ApkDiskIndex.page(
                apk, index, "", "AssetManifest.json", "Todos", 0, 120);
            assertEquals(1, tail.totalMatches);
            assertEquals("assets/flutter_assets/AssetManifest.json",
                tail.items.get(0).path);
            ApkDiskIndex.Page beyondPreview = ApkDiskIndex.page(
                apk, index, "", "item_239", "Todos", 0, 120);
            assertEquals(1, beyondPreview.totalMatches);
        } finally {
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }

    @Test public void securityReportListsStayCappedButCountsStayExact()
            throws Exception {
        File apk = archive();
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                add(out, "AndroidManifest.xml");
                add(out, "classes.dex");
                for (int i = 2; i <= 151; i++)
                    add(out, "classes" + i + ".dex");
                for (int i = 0; i < 155; i++)
                    add(out, String.format(Locale.ROOT,
                        "lib/arm64-v8a/lib%03d.so", i));
            }
            try (ZipFile zip = new ZipFile(apk)) {
                JSONObject security = SecurityScanner.scan(zip);
                assertEquals(307, security.getInt("entries"));
                assertEquals(151, security.getInt("dexFileCount"));
                assertEquals(155, security.getInt("nativeLibraryCount"));
                assertEquals(120, security.getJSONArray("dexFiles").length());
                assertEquals(120, security.getJSONArray("nativeLibraries").length());
                assertEquals(120, security.getJSONArray("fileExplorerPreview").length());
                assertTrue(security.getBoolean("filePreviewTruncated"));
            }
        } finally { apk.delete(); }
    }

    @Test public void standalonePreviewRejectsBadCrcBeforeReadingMetadata()
            throws Exception {
        File apk = archive();
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                add(out, "classes.dex");
                add(out, "assets/data.bin");
            }
            byte[] original = java.nio.file.Files.readAllBytes(apk.toPath());
            int header = -1;
            for (int i = 0; i < original.length - 46; i++)
                if (original[i] == 0x50 && original[i + 1] == 0x4b
                    && original[i + 2] == 0x01 && original[i + 3] == 0x02) {
                    header = i;
                    break;
                }
            assertTrue(header > 0);
            original[header + 16] ^= 1;
            java.nio.file.Files.write(apk.toPath(), original);
            try {
                ApkExplorer.inspect(apk);
                fail("Standalone explorer must not bypass CRC admission gate");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("CRC"));
            }
        } finally { apk.delete(); }
    }

    @Test public void indexFailureDoesNotDestroyTheOriginalArchive()
            throws Exception {
        File apk = archive();
        File index = new File(apk.getAbsolutePath() + ".idx.db");
        try {
            try (ZipOutputStream out = new ZipOutputStream(new FileOutputStream(apk))) {
                for (int i = 0; i < 130; i++)
                    add(out, String.format(Locale.ROOT, "assets/file_%03d.txt", i));
            }
            byte[] before = java.nio.file.Files.readAllBytes(apk.toPath());
            assertTrue(index.createNewFile());
            try {
                ApkDiskIndex.build(apk, index);
                fail("Index collision must fail instead of replacing prior data");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("existe"));
            }
            assertArrayEquals(before, java.nio.file.Files.readAllBytes(apk.toPath()));
        } finally {
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }
}
