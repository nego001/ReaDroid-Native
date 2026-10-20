package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

/** Synthetic ZIP fixtures. SQLite index is private, read-only for consumers. */
@RunWith(AndroidJUnit4.class)
public final class ApkDiskIndexInstrumentedTest {
    private File temp(String suffix) throws IOException {
        return File.createTempFile("readroid_idx_", suffix,
            InstrumentationRegistry.getInstrumentation().getTargetContext().getCacheDir());
    }

    private static void add(ZipOutputStream zip, String name) throws IOException {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(new byte[]{1, 2, 3});
        zip.closeEntry();
    }

    @Test public void paginatesThreeHundredItemsAndSearchesWithoutFullJsonList()
            throws Exception {
        File archive = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                add(zip, "AndroidManifest.xml");
                for (int i = 0; i < 301; i++) {
                    add(zip, String.format(Locale.ROOT, "assets/group/sample_%03d.txt", i));
                }
            }
            long original = archive.length();
            ApkDiskIndex.Stats stats = ApkDiskIndex.build(archive, index);
            assertEquals(302, stats.files);
            assertTrue(stats.databaseBytes > 0);
            ApkDiskIndex.Page root = ApkDiskIndex.page(archive, index,
                "", "", "Todos", 0, 120);
            assertEquals(2, root.totalMatches); // Manifest + implicit assets folder.
            assertTrue(root.items.stream().anyMatch(item ->
                item.directory && item.path.equals("assets/")));
            ApkDiskIndex.Page child = ApkDiskIndex.page(archive, index,
                "assets/", "", "Todos", 0, 120);
            assertEquals(1, child.totalMatches);
            assertEquals("assets/group/", child.items.get(0).path);
            ApkDiskIndex.Page one = ApkDiskIndex.page(archive, index,
                "assets/group/", "", "Todos", 0, 120);
            ApkDiskIndex.Page two = ApkDiskIndex.page(archive, index,
                "assets/group/", "", "Todos", 120, 120);
            ApkDiskIndex.Page three = ApkDiskIndex.page(archive, index,
                "assets/group/", "", "Todos", 240, 120);
            assertEquals(301, one.totalMatches);
            assertEquals(120, one.items.size());
            assertEquals(120, two.items.size());
            assertEquals(61, three.items.size());
            assertEquals("sample_000.txt", one.items.get(0).name);
            assertEquals("sample_300.txt", three.items.get(60).name);
            ApkDiskIndex.Page search = ApkDiskIndex.page(archive, index,
                "", "sample_300", "Todos", 0, 120);
            assertEquals(1, search.totalMatches);
            assertEquals("sample_300.txt", search.items.get(0).name);
            assertEquals(original, archive.length());
        } finally {
            archive.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void createsImplicitFoldersAndPreservesExplicitDirectory()
            throws Exception {
        File archive = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                add(zip, "assets/nested/file.bin");
                zip.putNextEntry(new ZipEntry("assets/"));
                zip.closeEntry();
            }
            ApkDiskIndex.build(archive, index);
            ApkDiskIndex.Page root = ApkDiskIndex.page(archive, index,
                "", "", "Todos", 0, 120);
            assertEquals(1, root.totalMatches);
            assertEquals("assets/", root.items.get(0).path);
            assertTrue(root.items.get(0).directory);
        } finally {
            archive.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void malformedPathRollsBackAndRemovesPartialIndex()
            throws Exception {
        File archive = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                add(zip, "assets/ok.txt");
                add(zip, "../bad.txt");
            }
            try {
                ApkDiskIndex.build(archive, index);
                fail("Traversal must fail before an index becomes available");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("inseguro"));
                assertFalse("Partial DB must be removed", index.exists());
            }
        } finally {
            archive.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void refusesExistingIndexAndUnboundedPages() throws Exception {
        File archive = temp(".apk");
        File index = temp(".db");
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                add(zip, "file.txt");
            }
            try {
                ApkDiskIndex.build(archive, index);
                fail("Existing indexes cannot be overwritten");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("existe"));
            }
            index.delete();
            ApkDiskIndex.build(archive, index);
            try {
                ApkDiskIndex.page(archive, index, "", "", "Todos", 0, 121);
                fail("Oversized page must be blocked");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("Paginação"));
            }
        } finally {
            archive.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void builtIndexRemainsBoundedAndReadableAfterReopen() throws Exception {
        File archive = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                add(zip, "assets/ok.json");
            }
            ApkDiskIndex.Stats stats = ApkDiskIndex.build(archive, index);
            // SQLite max_page_count is connection-local: a separate read-only
            // connection will show its own maximum, not the builder's quota.
            // build() checks the active writer quota and the final DB size.
            assertTrue("Index size must be bounded", index.length() <= 128L * 1024 * 1024);
            assertEquals(index.length(), stats.databaseBytes);
            ApkDiskIndex.Page page = ApkDiskIndex.page(
                archive, index, "assets/", "", "Todos", 0, 120);
            assertEquals(1, page.totalMatches);
            assertEquals("assets/ok.json", page.items.get(0).path);
        } finally {
            archive.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }

    @Test public void changedSourceCannotReuseIndex() throws Exception {
        File archive = temp(".apk");
        File index = temp(".db");
        index.delete();
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
                add(zip, "file.bin");
            }
            ApkDiskIndex.build(archive, index);
            try (FileOutputStream out = new FileOutputStream(archive, true)) {
                out.write(new byte[]{8, 9, 10});
            }
            try {
                ApkDiskIndex.page(archive, index, "", "", "Todos", 0, 120);
                fail("Modified source cannot use stale index");
            } catch (IOException expected) {
                assertTrue(expected.getMessage().contains("outra versão"));
            }
        } finally {
            archive.delete();
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
        }
    }
}
