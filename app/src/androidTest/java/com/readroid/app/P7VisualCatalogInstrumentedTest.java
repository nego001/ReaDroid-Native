package com.readroid.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.widget.LinearLayout;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** P7 layout and presets: actual preference writes, no APK or security mutation. */
@RunWith(AndroidJUnit4.class)
public final class P7VisualCatalogInstrumentedTest {
    @Test public void listLayoutIsPersistedAndChangesRealHomeAndSettingsViews() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences p = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hadLayout = p.contains("layout_variant");
        int previous = p.getInt("layout_variant", 0);
        boolean hadCompact = p.contains("compact");
        boolean wasCompact = p.getBoolean("compact", false);
        boolean hadRadius = p.contains("card_radius");
        int wasRadius = p.getInt("card_radius", 18);
        boolean hadPreset = p.contains("p7_active_preset");
        int wasPreset = p.getInt("p7_active_preset", -1);
        try {
            assertEquals(7, P7VisualCatalog.LAYOUT_NAMES.length);
            P7VisualCatalog.persistLayout(context, 3);
            assertEquals(3, P7VisualCatalog.currentLayout(context));
            assertFalse(p.getBoolean("compact", true));
            NegrescoTheme.apply(context);
            assertEquals(3, NegrescoTheme.LAYOUT_VARIANT);
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    LinearLayout grid = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(grid);
                    assertEquals(6, grid.getChildCount());
                    for (int i = 0; i < grid.getChildCount(); i++) {
                        LinearLayout row = (LinearLayout) grid.getChildAt(i);
                        assertEquals(1, row.getChildCount());
                        assertTrue(row.getChildAt(0).isClickable());
                        assertEquals(-1, row.getChildAt(0).getLayoutParams().width);
                    }
                    LinearLayout options = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-personalization-options");
                    assertNotNull(options);
                    assertEquals(13, options.getChildCount());
                    for (int i = 0; i < options.getChildCount(); i++)
                        assertEquals(1,
                            ((LinearLayout) options.getChildAt(i)).getChildCount());
                });
                P7VisualCatalog.persistLayout(context, 0);
                scenario.recreate();
                scenario.onActivity(activity -> {
                    LinearLayout grid = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertEquals(2, grid.getChildCount());
                    for (int i = 0; i < grid.getChildCount(); i++)
                        assertEquals(3,
                            ((LinearLayout) grid.getChildAt(i)).getChildCount());
                });
            }
            try {
                P7VisualCatalog.persistLayout(context, 6);
                fail("Invalid layout was applied");
            } catch (IllegalArgumentException expected) {
                assertEquals(0, P7VisualCatalog.currentLayout(context));
            }
        } finally {
            SharedPreferences.Editor editor = p.edit();
            if (hadLayout) editor.putInt("layout_variant", previous);
            else editor.remove("layout_variant");
            if (hadCompact) editor.putBoolean("compact", wasCompact);
            else editor.remove("compact");
            if (hadRadius) editor.putInt("card_radius", wasRadius);
            else editor.remove("card_radius");
            if (hadPreset) editor.putInt("p7_active_preset", wasPreset);
            else editor.remove("p7_active_preset");
            assertTrue(editor.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void twoColumnLayoutActuallyReflowsSixActionCards() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hadLayout = prefs.contains("layout_variant");
        int previous = prefs.getInt("layout_variant", 0);
        boolean hadCompact = prefs.contains("compact");
        boolean compact = prefs.getBoolean("compact", false);
        boolean hadRadius = prefs.contains("card_radius");
        int radius = prefs.getInt("card_radius", 18);
        boolean hadPreset = prefs.contains("p7_active_preset");
        int preset = prefs.getInt("p7_active_preset", -1);
        try {
            assertEquals(3, P7VisualCatalog.quickActionColumns(0));
            assertEquals(1, P7VisualCatalog.quickActionColumns(3));
            assertEquals(2, P7VisualCatalog.quickActionColumns(4));
            P7VisualCatalog.persistLayout(context, 4);
            assertEquals(4, P7VisualCatalog.currentLayout(context));
            assertFalse(prefs.getBoolean("compact", true));
            NegrescoTheme.apply(context);
            assertEquals(4, NegrescoTheme.LAYOUT_VARIANT);
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    LinearLayout quick = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(quick);
                    assertEquals("Six actions in three rows", 3, quick.getChildCount());
                    for (int rowIndex = 0; rowIndex < quick.getChildCount(); rowIndex++) {
                        LinearLayout row = (LinearLayout) quick.getChildAt(rowIndex);
                        assertEquals("Each row has two actions", 2, row.getChildCount());
                        for (int col = 0; col < row.getChildCount(); col++) {
                            android.view.View button = row.getChildAt(col);
                            assertTrue(button.isClickable());
                            assertTrue(button.isFocusable());
                            LinearLayout.LayoutParams params =
                                (LinearLayout.LayoutParams) button.getLayoutParams();
                            assertEquals(0, params.width);
                            assertEquals(1f, params.weight, 0.001f);
                        }
                    }
                    LinearLayout options = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-personalization-options");
                    assertNotNull(options);
                    assertEquals("Personalization stays in the standard two columns",
                        7, options.getChildCount());
                });
                P7VisualCatalog.persistLayout(context, 0);
                scenario.recreate();
                scenario.onActivity(activity -> {
                    LinearLayout quick = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(quick);
                    assertEquals(2, quick.getChildCount());
                    for (int row = 0; row < quick.getChildCount(); row++)
                        assertEquals(3, ((LinearLayout) quick.getChildAt(row)).getChildCount());
                });
            }
        } finally {
            SharedPreferences.Editor edit = prefs.edit();
            if (hadLayout) edit.putInt("layout_variant", previous);
            else edit.remove("layout_variant");
            if (hadCompact) edit.putBoolean("compact", compact);
            else edit.remove("compact");
            if (hadRadius) edit.putInt("card_radius", radius);
            else edit.remove("card_radius");
            if (hadPreset) edit.putInt("p7_active_preset", preset);
            else edit.remove("p7_active_preset");
            assertTrue(edit.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void twoColumnMiniatureDiffersFromListAndStandard() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        Bitmap[] images = new Bitmap[3];
        try {
            int[] variants = {0, 3, 4};
            for (int i = 0; i < variants.length; i++) {
                images[i] = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
                P7ThemePreviewView preview = new P7ThemePreviewView(
                    context, 0xff9b6dff, 1, variants[i], false);
                preview.layout(0, 0, 100, 100);
                preview.draw(new Canvas(images[i]));
            }
            assertFalse("Two-column preview must not repeat standard preview",
                images[2].sameAs(images[0]));
            assertFalse("Two-column preview must not repeat list preview",
                images[2].sameAs(images[1]));
        } finally {
            for (Bitmap image : images)
                if (image != null) image.recycle();
        }
    }

    @Test public void featuredModeKeepsTwoPrimaryActionsFullWidthAndFourAccessible()
            throws Exception {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hasLayout = prefs.contains("layout_variant");
        int previousLayout = prefs.getInt("layout_variant", 0);
        boolean hasCompact = prefs.contains("compact");
        boolean previousCompact = prefs.getBoolean("compact", false);
        boolean hasRadius = prefs.contains("card_radius");
        int previousRadius = prefs.getInt("card_radius", 18);
        boolean hasPreset = prefs.contains("p7_active_preset");
        int previousPreset = prefs.getInt("p7_active_preset", -1);
        try {
            assertArrayEquals(new int[]{3, 3}, P7VisualCatalog.quickActionRowSizes(0));
            assertArrayEquals(new int[]{1, 1, 1, 1, 1, 1},
                P7VisualCatalog.quickActionRowSizes(3));
            assertArrayEquals(new int[]{2, 2, 2},
                P7VisualCatalog.quickActionRowSizes(4));
            assertArrayEquals(new int[]{1, 1, 2, 2},
                P7VisualCatalog.quickActionRowSizes(5));
            P7VisualCatalog.persistLayout(context, 5);
            assertEquals(5, P7VisualCatalog.currentLayout(context));
            NegrescoTheme.apply(context);
            assertEquals(5, NegrescoTheme.LAYOUT_VARIANT);
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    LinearLayout grid = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(grid);
                    int[] expected = {1, 1, 2, 2};
                    String[] primary = {"Abrir APK", "Analisar"};
                    int total = 0;
                    assertEquals(expected.length, grid.getChildCount());
                    for (int rowIndex = 0; rowIndex < expected.length; rowIndex++) {
                        LinearLayout row = (LinearLayout) grid.getChildAt(rowIndex);
                        assertEquals(expected[rowIndex], row.getChildCount());
                        for (int col = 0; col < row.getChildCount(); col++) {
                            android.view.View action = row.getChildAt(col);
                            assertTrue(action.isClickable());
                            assertTrue(action.isFocusable());
                            LinearLayout.LayoutParams size =
                                (LinearLayout.LayoutParams) action.getLayoutParams();
                            if (expected[rowIndex] == 1) {
                                assertEquals(-1, size.width);
                                assertEquals(primary[rowIndex],
                                    action.getContentDescription().toString());
                            } else {
                                assertEquals(0, size.width);
                                assertEquals(1f, size.weight, 0.001f);
                            }
                            total++;
                        }
                    }
                    assertEquals("No existing action may disappear", 6, total);
                });
                P7VisualCatalog.persistLayout(context, 0);
                scenario.recreate();
                scenario.onActivity(activity -> {
                    LinearLayout grid = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(grid);
                    assertEquals(2, grid.getChildCount());
                    for (int row = 0; row < grid.getChildCount(); row++)
                        assertEquals(3,
                            ((LinearLayout) grid.getChildAt(row)).getChildCount());
                });
            }
            try {
                P7VisualCatalog.persistLayout(context, 7);
                fail("Invalid layout index beyond catalogue should be rejected");
            } catch (IllegalArgumentException expected) {
                assertEquals(0, P7VisualCatalog.currentLayout(context));
            }
        } finally {
            SharedPreferences.Editor restore = prefs.edit();
            if (hasLayout) restore.putInt("layout_variant", previousLayout);
            else restore.remove("layout_variant");
            if (hasCompact) restore.putBoolean("compact", previousCompact);
            else restore.remove("compact");
            if (hasRadius) restore.putInt("card_radius", previousRadius);
            else restore.remove("card_radius");
            if (hasPreset) restore.putInt("p7_active_preset", previousPreset);
            else restore.remove("p7_active_preset");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void featuredMiniatureReallyDiffersFromListAndTwoColumns() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        Bitmap featured = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        Bitmap list = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        Bitmap columns = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        try {
            P7ThemePreviewView a = new P7ThemePreviewView(
                context, 0xffffa24a, 1, 5, false);
            P7ThemePreviewView b = new P7ThemePreviewView(
                context, 0xffffa24a, 1, 3, false);
            P7ThemePreviewView c = new P7ThemePreviewView(
                context, 0xffffa24a, 1, 4, false);
            a.layout(0, 0, 100, 100);
            b.layout(0, 0, 100, 100);
            c.layout(0, 0, 100, 100);
            a.draw(new Canvas(featured));
            b.draw(new Canvas(list));
            c.draw(new Canvas(columns));
            assertFalse(featured.sameAs(list));
            assertFalse(featured.sameAs(columns));
        } finally {
            featured.recycle();
            list.recycle();
            columns.recycle();
        }
    }

    @Test public void workflowModeActuallyUsesOneTwoThreeCardsInThatOrder() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hadLayout = prefs.contains("layout_variant");
        int previous = prefs.getInt("layout_variant", 0);
        boolean hadCompact = prefs.contains("compact");
        boolean compact = prefs.getBoolean("compact", false);
        boolean hadRadius = prefs.contains("card_radius");
        int radius = prefs.getInt("card_radius", 18);
        boolean hadPreset = prefs.contains("p7_active_preset");
        int preset = prefs.getInt("p7_active_preset", -1);
        try {
            assertArrayEquals(new int[]{1, 2, 3},
                P7VisualCatalog.quickActionRowSizes(6));
            assertArrayEquals(new int[]{1, 1, 2, 2},
                P7VisualCatalog.quickActionRowSizes(5));
            P7VisualCatalog.persistLayout(context, 6);
            assertEquals(6, P7VisualCatalog.currentLayout(context));
            NegrescoTheme.apply(context);
            assertEquals(6, NegrescoTheme.LAYOUT_VARIANT);
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    LinearLayout actions = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(actions);
                    int[] rowSizes = {1, 2, 3};
                    String[] order = {"Abrir APK", "Analisar", "Build APK",
                        "Decompilar", "Editar Smali", "Assinar APK"};
                    assertEquals(3, actions.getChildCount());
                    int visited = 0;
                    for (int r = 0; r < rowSizes.length; r++) {
                        LinearLayout row = (LinearLayout) actions.getChildAt(r);
                        assertEquals(rowSizes[r], row.getChildCount());
                        for (int col = 0; col < row.getChildCount(); col++) {
                            android.view.View card = row.getChildAt(col);
                            assertTrue(card.isClickable());
                            assertTrue(card.isFocusable());
                            assertEquals(order[visited++],
                                card.getContentDescription().toString());
                            LinearLayout.LayoutParams params =
                                (LinearLayout.LayoutParams) card.getLayoutParams();
                            if (r == 0) assertEquals(-1, params.width);
                            else {
                                assertEquals(0, params.width);
                                assertEquals(1f, params.weight, 0.001f);
                            }
                        }
                    }
                    assertEquals(6, visited);
                });
                P7VisualCatalog.persistLayout(context, 0);
                scenario.recreate();
                scenario.onActivity(activity -> {
                    LinearLayout actions = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-quick-actions-grid");
                    assertNotNull(actions);
                    assertEquals(2, actions.getChildCount());
                    for (int r = 0; r < actions.getChildCount(); r++)
                        assertEquals(3,
                            ((LinearLayout) actions.getChildAt(r)).getChildCount());
                });
            }
            try {
                P7VisualCatalog.persistLayout(context, 7);
                fail("Seventh-index nonexistent layout accepted");
            } catch (IllegalArgumentException expected) {
                assertEquals(0, P7VisualCatalog.currentLayout(context));
            }
        } finally {
            SharedPreferences.Editor restore = prefs.edit();
            if (hadLayout) restore.putInt("layout_variant", previous);
            else restore.remove("layout_variant");
            if (hadCompact) restore.putBoolean("compact", compact);
            else restore.remove("compact");
            if (hadRadius) restore.putInt("card_radius", radius);
            else restore.remove("card_radius");
            if (hadPreset) restore.putInt("p7_active_preset", preset);
            else restore.remove("p7_active_preset");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void workflowMiniatureIsNotTheFeaturedOrTwoColumnPreview() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        Bitmap workflow = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        Bitmap featured = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        Bitmap columns = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        try {
            P7ThemePreviewView one = new P7ThemePreviewView(
                context, 0xff25bdd6, 1, 6, false);
            P7ThemePreviewView two = new P7ThemePreviewView(
                context, 0xff25bdd6, 1, 5, false);
            P7ThemePreviewView three = new P7ThemePreviewView(
                context, 0xff25bdd6, 1, 4, false);
            one.layout(0, 0, 100, 100);
            two.layout(0, 0, 100, 100);
            three.layout(0, 0, 100, 100);
            one.draw(new Canvas(workflow));
            two.draw(new Canvas(featured));
            three.draw(new Canvas(columns));
            assertFalse(workflow.sameAs(featured));
            assertFalse(workflow.sameAs(columns));
        } finally {
            workflow.recycle();
            featured.recycle();
            columns.recycle();
        }
    }

    @Test public void compactAndModernLayoutsPersistSafely() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                SharedPreferences p = activity.getSharedPreferences(
                    "v3_personalizacao", Context.MODE_PRIVATE);
                try {
                    P7VisualCatalog.applyLayout(activity, 1);
                    assertEquals(1, p.getInt("layout_variant", -1));
                    assertTrue(p.getBoolean("compact", false));
                    assertEquals(12, p.getInt("card_radius", -1));
                    P7VisualCatalog.applyLayout(activity, 2);
                    assertEquals(2, p.getInt("layout_variant", -1));
                    assertFalse(p.getBoolean("compact", true));
                    assertEquals(26, p.getInt("card_radius", -1));
                    try {
                        P7VisualCatalog.applyLayout(activity, -1);
                        fail("Unexpected layout accepted");
                    } catch (IllegalArgumentException expected) {
                        assertEquals(2, p.getInt("layout_variant", -1));
                    }
                } finally {
                    p.edit().remove("layout_variant").putBoolean("compact", false)
                        .putInt("card_radius", 18).commit();
                }
            });
        }
    }

    @Test public void presetWritesOnlyAppearanceAndRejectsOutOfRangeChoices() {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                SharedPreferences p = activity.getSharedPreferences(
                    "v3_personalizacao", Context.MODE_PRIVATE);
                SharedPreferences security = activity.getSharedPreferences(
                    "security_state", Context.MODE_PRIVATE);
                try {
                    assertTrue(security.edit().putString("p7_test_secret", "retain").commit());
                    P7VisualCatalog.applyPreset(activity, 1);
                    assertEquals("purple", p.getString("accent", ""));
                    assertTrue(p.getBoolean("studio_glow", false));
                    assertEquals(1, p.getInt("p7_active_preset", -1));
                    assertEquals("retain", security.getString("p7_test_secret", ""));
                    try {
                        P7VisualCatalog.applyPreset(activity, 5);
                        fail("Invalid preset accepted");
                    } catch (IllegalArgumentException expected) {
                        assertEquals(1, p.getInt("p7_active_preset", -1));
                    }
                } finally {
                    security.edit().remove("p7_test_secret").commit();
                    p.edit().remove("p7_active_preset").putString("accent", "blue")
                        .putBoolean("studio_glow", true).commit();
                }
            });
        }
    }
}
