package com.readroid.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.net.Uri;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.ByteArrayOutputStream;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Tests the real icon renderer and the safe, opt-in PNG workflow. */
@RunWith(AndroidJUnit4.class)
public final class P7IconWorkshopInstrumentedTest {
    private static Bitmap render(P7IconWorkshop.Spec spec) {
        Bitmap bitmap = Bitmap.createBitmap(512, 512, Bitmap.Config.ARGB_8888);
        P7IconWorkshop.drawIcon(new Canvas(bitmap), spec,
            new Paint(Paint.ANTI_ALIAS_FLAG));
        return bitmap;
    }

    @Test public void producesDistinctSolidNativePngArtworkWithoutSourceApk() {
        Bitmap shield = render(new P7IconWorkshop.Spec(0, 0, 0));
        Bitmap code = render(new P7IconWorkshop.Spec(0, 1, 0));
        Bitmap circle = render(new P7IconWorkshop.Spec(0, 0, 1));
        Bitmap square = render(new P7IconWorkshop.Spec(0, 0, 2));
        Bitmap green = render(new P7IconWorkshop.Spec(1, 0, 0));
        try {
            assertEquals(512, shield.getWidth());
            assertEquals(512, shield.getHeight());
            assertNotEquals(0, Color.alpha(shield.getPixel(256, 256)));
            assertFalse("Glyph changes must alter the actual pixels",
                shield.sameAs(code));
            assertFalse("Palette changes must alter the actual pixels",
                shield.sameAs(green));
            assertEquals("The circle must have a transparent exterior",
                0, Color.alpha(circle.getPixel(47, 47)));
            assertEquals("The square needs solid pixels near the corner",
                255, Color.alpha(square.getPixel(52, 52)));
            assertEquals("Outside the icon must stay transparent",
                0, Color.alpha(shield.getPixel(0, 0)));
            ByteArrayOutputStream stream = new ByteArrayOutputStream();
            assertTrue(shield.compress(Bitmap.CompressFormat.PNG, 100, stream));
            byte[] data = stream.toByteArray();
            assertTrue(data.length > 1000);
            assertEquals(0x89, data[0] & 0xff);
            assertEquals('P', data[1]);
            assertEquals('N', data[2]);
            assertEquals('G', data[3]);
        } finally {
            shield.recycle(); code.recycle(); circle.recycle();
            square.recycle(); green.recycle();
        }
    }

    @Test public void rejectsInvalidOptionsAndNonSafDestinations() throws Exception {
        try {
            new P7IconWorkshop.Spec(-1, 0, 0);
            fail("Invalid background accepted");
        } catch (IllegalArgumentException expected) { }
        try {
            new P7IconWorkshop.Spec(0, 4, 0);
            fail("Invalid symbol accepted");
        } catch (IllegalArgumentException expected) { }
        Context context = InstrumentationRegistry.getInstrumentation()
            .getTargetContext();
        try {
            P7IconWorkshop.export(context,
                new P7IconWorkshop.Spec(0, 0, 0),
                Uri.parse("file:///sdcard/unauthorized.png"));
            fail("Unapproved URI schema accepted");
        } catch (java.io.IOException expected) { }
    }

    private static View byText(View view, String label) {
        if (view instanceof TextView &&
            label.equals(((TextView) view).getText().toString()) &&
            view.isClickable()) return view;
        if (view instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) view;
            for (int i = 0; i < parent.getChildCount(); i++) {
                View item = byText(parent.getChildAt(i), label);
                if (item != null) return item;
            }
        }
        return null;
    }

    @Test public void designStudioIconsTabOpensNativeWorkshop() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> {
                View root = a.getWindow().getDecorView();
                View design = findDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                View iconsTab = byText(root, "Ícones");
                assertNotNull(iconsTab);
                assertTrue(iconsTab.performClick());
                View create = byText(root,
                    "Abrir criador de ícones  ↗\nEscolher cores, símbolos e formato; exportar PNG 512×512");
                assertNotNull("The icon workshop must replace the placeholder",
                    create);
                assertTrue(create.isClickable());
                // Dialog owns a separate Window; inspect that window rather
                // than mistakenly querying the Activity's decor view.
                android.app.AlertDialog dialog = P7IconWorkshop.open(a);
                assertNotNull(findDescription(dialog.getWindow().getDecorView(),
                    "Prévia original do ícone"));
                dialog.dismiss();
            });
        }
    }

    private static View findDescription(View view, String label) {
        if (label.equals(view.getContentDescription())) return view;
        if (view instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) view;
            for (int i = 0; i < parent.getChildCount(); i++) {
                View item = findDescription(parent.getChildAt(i), label);
                if (item != null) return item;
            }
        }
        return null;
    }
}
