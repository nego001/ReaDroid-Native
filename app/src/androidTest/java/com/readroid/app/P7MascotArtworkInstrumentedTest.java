package com.readroid.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.util.Base64;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class P7MascotArtworkInstrumentedTest {
    @Test public void usesApprovedReferencePixelsNotOnlyFallbackVector() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        byte[] encoded;
        try (InputStream in = context.getAssets().open("p7_reference_mascot.webp.base64");
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[4096];
            int length;
            while ((length = in.read(chunk)) != -1) out.write(chunk, 0, length);
            encoded = out.toByteArray();
        }
        byte[] webp = Base64.decode(encoded, Base64.DEFAULT);
        assertEquals("Original approved crop must not be replaced silently",
            "0f5817509df5f6b19c01e9ab124d7667878a2bab5500e34954eb7d59ac1e0713",
            hex(MessageDigest.getInstance("SHA-256").digest(webp)));
        Bitmap bitmap = BitmapFactory.decodeByteArray(webp, 0, webp.length);
        assertNotNull("Original mascot must decode on this Android version", bitmap);
        assertEquals(160, bitmap.getWidth());
        assertTrue(bitmap.getHeight() > 200);
        assertTrue(new P7MascotView(context).usesApprovedArtwork());
        bitmap.recycle();
    }

    @Test public void approvedArtworkFadesIntoOledInsteadOfShowingSharpRectangle() {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        P7MascotView mascot = new P7MascotView(context);
        assertTrue(mascot.usesApprovedArtwork());
        mascot.layout(0, 0, 280, 360);
        Bitmap frame = Bitmap.createBitmap(280, 360, Bitmap.Config.ARGB_8888);
        try {
            mascot.draw(new Canvas(frame));
            int middleX = 210;
            int middleY = 210;
            int middleAlpha = Color.alpha(frame.getPixel(middleX, middleY));
            assertTrue("The mascot content must still be visible", middleAlpha > 60);
            // The approved source crop was a hard-edged opaque rectangle.
            // Both its lateral border and base must now fade to transparent.
            int leftAlpha = Color.alpha(frame.getPixel(126, middleY));
            int bottomAlpha = Color.alpha(frame.getPixel(middleX, 359));
            assertTrue("The left edge must blend into OLED", leftAlpha < middleAlpha / 3);
            assertTrue("The bottom edge must blend into OLED",
                bottomAlpha < middleAlpha / 3);
        } finally {
            frame.recycle();
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte item : bytes)
            result.append(String.format(java.util.Locale.ROOT, "%02x", item & 255));
        return result.toString();
    }
}
