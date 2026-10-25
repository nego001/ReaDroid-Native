package com.readroid.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.net.Uri;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/**
 * Authentic icons come from Android package resources of a real archive.
 * Missing icons, invalid ZIPs and ungranted URIs never become fake logos.
 */
@RunWith(AndroidJUnit4.class)
public final class P7RecentAppIconsInstrumentedTest {
    @Test public void androidCanExtractRealIconWithoutInstallingAnyArchive()
            throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File installedArchive = new File(context.getApplicationInfo().sourceDir);
        assertTrue(installedArchive.isFile());
        Bitmap icon = P7RecentAppIcons.extract(context, installedArchive);
        assertNotNull("The test APK declares a launcher icon", icon);
        try {
            assertEquals(64, icon.getWidth());
            assertEquals(64, icon.getHeight());
        } finally {
            icon.recycle();
        }
    }

    @Test public void untrustedOrUnpermittedArchiveNeverGetsCached() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File invalid = File.createTempFile("broken_app_", ".apk",
            context.getCacheDir());
        try {
            try (FileOutputStream out = new FileOutputStream(invalid)) {
                out.write("not-an-apk".getBytes(StandardCharsets.UTF_8));
            }
            assertNull(P7RecentAppIcons.extract(context, invalid));
            Uri denied = Uri.parse("content://ungranted.example/document/1");
            assertFalse(P7RecentAppIcons.capture(context, denied,
                new File(context.getApplicationInfo().sourceDir)));
            assertNull(P7RecentAppIcons.load(context, denied));
            assertFalse(P7RecentAppIcons.capture(context,
                Uri.parse("file:///private/app.apk"), invalid));
        } finally {
            invalid.delete();
        }
    }
}
