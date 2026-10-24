package com.readroid.app;

import android.content.Context;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Filters from the approved mockup must query the real paged index. */
@RunWith(AndroidJUnit4.class)
public final class P7IndexedFiltersInstrumentedTest {
    @Test public void editableFilterReadsFullIndexWithCorrectFileTypes() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File apk = File.createTempFile("p7_editable_", ".apk", context.getCacheDir());
        File index = new File(apk.getAbsolutePath() + ".db");
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                for (String path : new String[]{
                        "assets/first.txt", "assets/second.JSON",
                        "assets/deep/site.html", "assets/deep/app.js",
                        "assets/bin.dat", "classes.dex"}) {
                    zip.putNextEntry(new ZipEntry(path));
                    zip.write("a".getBytes(StandardCharsets.UTF_8));
                    zip.closeEntry();
                }
            }
            ApkDiskIndex.build(apk, index);
            ApkDiskIndex.Page root = ApkDiskIndex.page(
                apk, index, "", "", "Editáveis", 0, 120);
            assertEquals(1, root.totalMatches);
            assertTrue(root.items.get(0).directory);
            assertEquals("assets/", root.items.get(0).path);
            ApkDiskIndex.Page files = ApkDiskIndex.page(
                apk, index, "assets/", "", "Editáveis", 0, 120);
            assertEquals(3, files.totalMatches); // .txt, .JSON and deep/
            assertTrue(files.items.stream().anyMatch(item ->
                item.directory && item.path.equals("assets/deep/")));
            assertTrue(files.items.stream().anyMatch(item ->
                item.path.equals("assets/second.JSON")));
            ApkDiskIndex.Page global = ApkDiskIndex.page(
                apk, index, "", ".", "Editáveis", 0, 120);
            assertEquals(4, global.totalMatches);
            for (ApkDiskIndex.Item item : global.items)
                assertTrue(EditPlan.isEditable(item.path));
        } finally {
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }

    @Test public void matchesXmlImagesAndSmaliWithoutFabricatedResults() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File apk = File.createTempFile("p7_filters_", ".apk", context.getCacheDir());
        File index = new File(apk.getAbsolutePath() + ".db");
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(apk))) {
                for (String name : new String[]{
                        "assets/icon.png", "assets/picture.webp", "assets/note.txt",
                        "res/config.xml", "smali/com/example/Main.smali", "classes.dex"}) {
                    zip.putNextEntry(new ZipEntry(name));
                    zip.write("file".getBytes(StandardCharsets.UTF_8));
                    zip.closeEntry();
                }
            }
            ApkDiskIndex.build(apk, index);
            ApkDiskIndex.Page images = ApkDiskIndex.page(
                apk, index, "", ".", "Imagens", 0, 120);
            assertEquals(2, images.totalMatches);
            for (ApkDiskIndex.Item item : images.items)
                assertTrue(item.path.endsWith(".png") || item.path.endsWith(".webp"));

            ApkDiskIndex.Page xml = ApkDiskIndex.page(
                apk, index, "", ".", "XML", 0, 120);
            assertEquals(1, xml.totalMatches);
            assertEquals("res/config.xml", xml.items.get(0).path);

            ApkDiskIndex.Page smali = ApkDiskIndex.page(
                apk, index, "", ".", "Smali", 0, 120);
            assertEquals(1, smali.totalMatches);
            assertEquals("smali/com/example/Main.smali", smali.items.get(0).path);

            ApkDiskIndex.Page missing = ApkDiskIndex.page(
                apk, index, "", "does-not-exist", "Smali", 0, 120);
            assertTrue(missing.items.isEmpty());
            assertEquals(0, missing.totalMatches);
        } finally {
            android.database.sqlite.SQLiteDatabase.deleteDatabase(index);
            apk.delete();
        }
    }
}
