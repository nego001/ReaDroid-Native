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

/** Real native logo compositor, navigation and SAF permission contract. */
@RunWith(AndroidJUnit4.class)
public final class P7LogoWorkshopInstrumentedTest {
    private static Bitmap render(P7LogoWorkshop.Spec input) {
        Bitmap bitmap = Bitmap.createBitmap(
            P7LogoWorkshop.WIDTH, P7LogoWorkshop.HEIGHT, Bitmap.Config.ARGB_8888);
        P7LogoWorkshop.drawLogo(new Canvas(bitmap), input,
            new Paint(Paint.ANTI_ALIAS_FLAG));
        return bitmap;
    }

    @Test public void rendersDistinctPngColorsAndTransparencies() {
        P7LogoWorkshop.Spec sample = new P7LogoWorkshop.Spec(
            "NegrecoDroid", "APK ENGINEERING STUDIO", 0, 0);
        Bitmap transparent = render(sample);
        Bitmap violet = render(new P7LogoWorkshop.Spec(
            "NegrecoDroid", "APK ENGINEERING STUDIO", 1, 0));
        Bitmap opaque = render(new P7LogoWorkshop.Spec(
            "NegrecoDroid", "APK ENGINEERING STUDIO", 0, 1));
        Bitmap renamed = render(new P7LogoWorkshop.Spec(
            "Novo Logo", "APK ENGINEERING STUDIO", 0, 0));
        try {
            assertEquals(1024, transparent.getWidth());
            assertEquals(512, transparent.getHeight());
            assertEquals(0, Color.alpha(transparent.getPixel(0, 0)));
            assertEquals(0, Color.alpha(transparent.getPixel(50, 250)));
            assertEquals(255, Color.alpha(opaque.getPixel(50, 250)));
            assertEquals("OLED background must be opaque pure black at top-left",
                Color.BLACK, opaque.getPixel(0, 0));
            assertEquals("OLED background must be opaque pure black at bottom-right",
                Color.BLACK, opaque.getPixel(1023, 511));
            assertEquals("OLED background must not be the old navy shade",
                Color.BLACK, opaque.getPixel(500, 40));
            assertFalse("Transparency setting must change actual output",
                transparent.sameAs(opaque));
            assertFalse("Color must change actual PNG pixels",
                transparent.sameAs(violet));
            assertFalse("Name must change actual logo pixels",
                transparent.sameAs(renamed));
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            assertTrue(transparent.compress(Bitmap.CompressFormat.PNG, 100, output));
            byte[] png = output.toByteArray();
            assertTrue(png.length > 1000);
            assertEquals(0x89, png[0] & 0xff);
            assertEquals('P', png[1]);
            assertEquals('N', png[2]);
            assertEquals('G', png[3]);
        } finally {
            transparent.recycle();
            violet.recycle();
            opaque.recycle();
            renamed.recycle();
        }
    }

    @Test public void rejectsMalformedInputsAndNonSafExport() throws Exception {
        for (String name : new String[]{"", " ", "Texto\nperigoso",
                "abcdefghijklmnopqrstuvwxyzabcdef"}) {
            try {
                new P7LogoWorkshop.Spec(name, "Teste", 0, 0);
                fail("Invalid logo name accepted: " + name);
            } catch (IllegalArgumentException expected) { }
        }
        try {
            new P7LogoWorkshop.Spec("Logo", "Texto", 4, 0);
            fail("Out of range palette accepted");
        } catch (IllegalArgumentException expected) { }
        try {
            new P7LogoWorkshop.Spec("Logo", "Texto", 0, -1);
            fail("Out of range background accepted");
        } catch (IllegalArgumentException expected) { }
        Context context = InstrumentationRegistry.getInstrumentation()
            .getTargetContext();
        try {
            P7LogoWorkshop.export(context,
                new P7LogoWorkshop.Spec("Logo", "Teste", 0, 0),
                Uri.parse("file:///sdcard/sem-permissao.png"));
            fail("Unsafe destination accepted");
        } catch (java.io.IOException expected) { }
    }

    private static View findDescription(View view, String description) {
        CharSequence label = view.getContentDescription();
        if (label != null && (description.equals(label.toString())
                || ("Abrir seção Design".equals(description)
                    && label.toString().startsWith("Seção Design")))) return view;
        if (view instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) view;
            for (int i = 0; i < parent.getChildCount(); i++) {
                View found = findDescription(parent.getChildAt(i), description);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static View findClickText(View view, String text) {
        if (view instanceof TextView
                && text.equals(((TextView) view).getText().toString())
                && view.isClickable()) return view;
        if (view instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) view;
            for (int i = 0; i < parent.getChildCount(); i++) {
                View found = findClickText(parent.getChildAt(i), text);
                if (found != null) return found;
            }
        }
        return null;
    }

    @Test public void logoStudioOpensRealEditorWithoutModifyingSavedIdentity() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> {
                String saved = a.getSharedPreferences("v3_personalizacao",
                    Context.MODE_PRIVATE).getString("display_name", "NegrecoDroid");
                View root = a.getWindow().getDecorView();
                View design = findDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                View tab = findClickText(root, "Logotipo");
                assertNotNull(tab);
                assertTrue(tab.performClick());
                assertNotNull("Logo Studio must offer a real editor",
                    findClickText(root,
                        "Criar logo PNG  ↗\nPersonalizar texto, cor e fundo; exportar PNG 1024×512"));
                android.app.AlertDialog dialog = P7LogoWorkshop.open(a);
                try {
                    View dialogRoot = dialog.getWindow().getDecorView();
                    assertNotNull(findDescription(dialogRoot, "Prévia original do logo"));
                    View exportButton = findDescription(dialogRoot,
                        "Exportar logo PNG 1024×512");
                    assertNotNull(exportButton);
                    assertTrue(exportButton.isClickable());
                    assertNotNull("SVG vector export must have a real action",
                        findDescription(dialogRoot, "Exportar logo SVG vetorial"));
                    assertNotNull(findDescription(dialogRoot, "Nome do logo"));
                    assertNotNull(findDescription(dialogRoot, "Subtítulo do logo"));
                } finally {
                    dialog.dismiss();
                }
                assertEquals("Closing the editor must not change app identity", saved,
                    a.getSharedPreferences("v3_personalizacao",
                        Context.MODE_PRIVATE)
                        .getString("display_name", "NegrecoDroid"));
            });
        }
    }

    @Test public void logoWorkshopUsesStudioPaletteAndDistinctExportStyles() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                android.app.AlertDialog dialog = P7LogoWorkshop.open(activity);
                try {
                    View decor = dialog.getWindow().getDecorView();
                    assertTrue("Logo panel should use a native themed shape",
                        decor.getBackground()
                        instanceof android.graphics.drawable.GradientDrawable);
                    android.graphics.drawable.GradientDrawable panel =
                        (android.graphics.drawable.GradientDrawable)
                            decor.getBackground();
                    assertEquals(NegrescoTheme.SURFACE,
                        panel.getColor().getDefaultColor());
                    assertEquals(NegrescoTheme.ACCENT,
                        dialog.getButton(android.app.AlertDialog.BUTTON_NEGATIVE)
                            .getCurrentTextColor());
                    android.widget.Button png = (android.widget.Button)
                        findDescription(decor, "Exportar logo PNG 1024×512");
                    android.widget.Button svg = (android.widget.Button)
                        findDescription(decor, "Exportar logo SVG vetorial");
                    assertNotNull(png);
                    assertNotNull(svg);
                    assertTrue(png.isClickable());
                    assertTrue(svg.isClickable());
                    assertEquals(NegrescoTheme.ON_ACCENT, png.getCurrentTextColor());
                    assertEquals(NegrescoTheme.TEXT, svg.getCurrentTextColor());
                    assertTrue(png.getBackground()
                        instanceof android.graphics.drawable.GradientDrawable);
                    assertTrue(svg.getBackground()
                        instanceof android.graphics.drawable.GradientDrawable);
                } finally {
                    dialog.dismiss();
                }
            });
        }
    }

}
