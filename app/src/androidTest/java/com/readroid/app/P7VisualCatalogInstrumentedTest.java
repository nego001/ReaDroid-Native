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
            assertEquals(12, P7VisualCatalog.LAYOUT_NAMES.length);
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
                P7VisualCatalog.persistLayout(context,
                    P7VisualCatalog.LAYOUT_NAMES.length);
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

    @Test public void primaryLayoutMiniaturesReflectRealDensityAndRadius() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        Bitmap[] previews = new Bitmap[3];
        try {
            for (int layout = 0; layout < 3; layout++) {
                assertArrayEquals("Primary layouts keep actual 3x2 actions",
                    new int[]{3, 3}, P7VisualCatalog.quickActionRowSizes(layout));
                previews[layout] = Bitmap.createBitmap(
                    100, 100, Bitmap.Config.ARGB_8888);
                P7ThemePreviewView view = new P7ThemePreviewView(
                    context, 0xff1688ff, 1, layout, false);
                view.layout(0, 0, 100, 100);
                view.draw(new Canvas(previews[layout]));
            }
            assertFalse("Compact must not look identical to Standard",
                previews[0].sameAs(previews[1]));
            assertFalse("Modern roundness/spacing must differ from Standard",
                previews[0].sameAs(previews[2]));
            assertFalse("Compact must not look identical to Modern",
                previews[1].sameAs(previews[2]));
            assertEquals("Compact shows its denser first card earlier",
                0xff20364d, previews[1].getPixel(30, 31));
            assertEquals("Standard keeps extra breathing room",
                0xff07101d, previews[0].getPixel(30, 31));
        } finally {
            for (Bitmap preview : previews)
                if (preview != null) preview.recycle();
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
                P7VisualCatalog.persistLayout(context,
                    P7VisualCatalog.LAYOUT_NAMES.length);
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
                P7VisualCatalog.persistLayout(context,
                    P7VisualCatalog.LAYOUT_NAMES.length);
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

    @Test public void fiveAdditionalLayoutsHaveUniqueFunctionalRowGeometry() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hadLayout = prefs.contains("layout_variant");
        int originalLayout = prefs.getInt("layout_variant", 0);
        boolean hadCompact = prefs.contains("compact");
        boolean originalCompact = prefs.getBoolean("compact", false);
        boolean hadRadius = prefs.contains("card_radius");
        int originalRadius = prefs.getInt("card_radius", 18);
        boolean hadPreset = prefs.contains("p7_active_preset");
        int originalPreset = prefs.getInt("p7_active_preset", -1);
        int[][] expectedRows = {
            {1, 3, 2}, {2, 1, 3}, {2, 3, 1}, {3, 1, 2}, {3, 2, 1}
        };
        try {
            assertEquals(12, P7VisualCatalog.LAYOUT_NAMES.length);
            P7VisualCatalog.persistLayout(context, 7);
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                for (int i = 0; i < expectedRows.length; i++) {
                    final int index = 7 + i;
                    final int[] expected = expectedRows[i];
                    if (i > 0) {
                        P7VisualCatalog.persistLayout(context, index);
                        scenario.recreate();
                    }
                    assertArrayEquals(expected,
                        P7VisualCatalog.quickActionRowSizes(index));
                    assertEquals(index, P7VisualCatalog.currentLayout(context));
                    scenario.onActivity(activity -> {
                        assertEquals(index, NegrescoTheme.LAYOUT_VARIANT);
                        LinearLayout actions = activity.getWindow().getDecorView()
                            .findViewWithTag("p7-quick-actions-grid");
                        assertNotNull(actions);
                        assertEquals(expected.length, actions.getChildCount());
                        String[] labels = {"Abrir APK", "Analisar", "Build APK",
                            "Decompilar", "Editar Smali", "Assinar APK"};
                        int at = 0;
                        for (int rowIndex = 0; rowIndex < expected.length; rowIndex++) {
                            LinearLayout row = (LinearLayout) actions.getChildAt(rowIndex);
                            assertEquals(expected[rowIndex], row.getChildCount());
                            for (int col = 0; col < row.getChildCount(); col++) {
                                android.view.View action = row.getChildAt(col);
                                assertTrue(action.isClickable());
                                assertTrue(action.isFocusable());
                                assertEquals(labels[at++],
                                    action.getContentDescription().toString());
                                LinearLayout.LayoutParams lp =
                                    (LinearLayout.LayoutParams) action.getLayoutParams();
                                if (expected[rowIndex] == 1) assertEquals(-1, lp.width);
                                else {
                                    assertEquals(0, lp.width);
                                    assertEquals(1f, lp.weight, 0.001f);
                                }
                            }
                        }
                        assertEquals(6, at);
                    });
                }
            }
            try {
                P7VisualCatalog.persistLayout(context,
                    P7VisualCatalog.LAYOUT_NAMES.length);
                fail("An out-of-range layout must be rejected");
            } catch (IllegalArgumentException expected) {
                assertEquals(11, P7VisualCatalog.currentLayout(context));
            }
        } finally {
            SharedPreferences.Editor restore = prefs.edit();
            if (hadLayout) restore.putInt("layout_variant", originalLayout);
            else restore.remove("layout_variant");
            if (hadCompact) restore.putBoolean("compact", originalCompact);
            else restore.remove("compact");
            if (hadRadius) restore.putInt("card_radius", originalRadius);
            else restore.remove("card_radius");
            if (hadPreset) restore.putInt("p7_active_preset", originalPreset);
            else restore.remove("p7_active_preset");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void fiveAdditionalPreviewsAreActuallyDistinct() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        Bitmap[] image = new Bitmap[5];
        try {
            for (int i = 0; i < image.length; i++) {
                image[i] = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
                P7ThemePreviewView preview = new P7ThemePreviewView(
                    context, 0xff25bdd6, 1, 7 + i, false);
                preview.layout(0, 0, 100, 100);
                preview.draw(new Canvas(image[i]));
                for (int earlier = 0; earlier < i; earlier++) {
                    assertFalse("Different grid structures must look different",
                        image[i].sameAs(image[earlier]));
                }
            }
        } finally {
            for (Bitmap bitmap : image) if (bitmap != null) bitmap.recycle();
        }
    }

    @Test public void narrowAndLargeTextReflowNeverDropsAnyAction() {
        assertArrayEquals(new int[]{3, 3},
            P7VisualCatalog.quickActionRowsForViewport(0, 393, 1f, 1f));
        assertArrayEquals(new int[]{2, 2, 2},
            P7VisualCatalog.quickActionRowsForViewport(0, 340, 1f, 1f));
        assertArrayEquals(new int[]{1, 1, 1, 1, 1, 1},
            P7VisualCatalog.quickActionRowsForViewport(0, 319, 1f, 1f));
        assertArrayEquals(new int[]{2, 2, 2},
            P7VisualCatalog.quickActionRowsForViewport(0, 393, 1.25f, 1f));
        assertArrayEquals(new int[]{1, 1, 1, 1, 1, 1},
            P7VisualCatalog.quickActionRowsForViewport(0, 393, 1.25f, 1.3f));
        assertArrayEquals(new int[]{1, 1, 1, 1, 1, 1},
            P7VisualCatalog.quickActionRowsForViewport(3, 340, 1f, 1f));
        assertArrayEquals(new int[]{1, 1, 2, 2},
            P7VisualCatalog.quickActionRowsForViewport(5, 350, 1f, 1f));
        for (int layout = 0; layout < P7VisualCatalog.LAYOUT_NAMES.length; layout++) {
            for (int width : new int[]{280, 319, 320, 340, 393, 600}) {
                int[] rows = P7VisualCatalog.quickActionRowsForViewport(
                    layout, width, 1.4f, 1.2f);
                int actions = 0;
                for (int columns : rows) {
                    assertTrue(columns >= 1 && columns <= 3);
                    actions += columns;
                }
                assertEquals("Reflow cannot drop or duplicate actions", 6, actions);
            }
        }
    }

    @Test public void nativeAdaptiveGridKeepsAllLabelsAndClickHandlers() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                String[] labels = {"Abrir APK", "Analisar", "Build APK",
                    "Decompilar", "Editar Smali", "Assinar APK"};
                int[] icons = {
                    R.drawable.ic_p7_folder, R.drawable.ic_p7_search,
                    R.drawable.ic_p7_wrench, R.drawable.ic_p7_code,
                    R.drawable.ic_p7_file, R.drawable.ic_p7_shield
                };
                int[] clicked = new int[6];
                android.view.View.OnClickListener[] actions =
                    new android.view.View.OnClickListener[6];
                for (int i = 0; i < actions.length; i++) {
                    final int index = i;
                    actions[i] = view -> clicked[index]++;
                }
                LinearLayout grid = new LinearLayout(activity);
                grid.setOrientation(LinearLayout.VERTICAL);
                P7ActionGrid.populate(activity, grid, labels, icons, actions,
                    6, 340, 1f, 1f);
                assertEquals(3, grid.getChildCount());
                int at = 0;
                for (int rowIndex = 0; rowIndex < grid.getChildCount(); rowIndex++) {
                    LinearLayout row = (LinearLayout) grid.getChildAt(rowIndex);
                    assertEquals(2, row.getChildCount());
                    for (int col = 0; col < row.getChildCount(); col++) {
                        android.view.View tile = row.getChildAt(col);
                        assertEquals(labels[at], tile.getContentDescription().toString());
                        assertTrue(tile.isClickable());
                        assertTrue(tile.isFocusable());
                        assertTrue("Existing actions must keep their callbacks",
                            tile.performClick());
                        at++;
                    }
                }
                assertEquals(6, at);
                for (int count : clicked) assertEquals(1, count);

                // With larger text the exact same actions must stack vertically.
                P7ActionGrid.populate(activity, grid, labels, icons, actions,
                    6, 393, 1.25f, 1.3f);
                assertEquals(6, grid.getChildCount());
                for (int row = 0; row < 6; row++) {
                    LinearLayout cell = (LinearLayout) grid.getChildAt(row);
                    assertEquals(1, cell.getChildCount());
                    assertEquals(-1, cell.getChildAt(0).getLayoutParams().width);
                    assertEquals(labels[row],
                        cell.getChildAt(0).getContentDescription().toString());
                }
            });
        }
    }

    @Test public void allQuickActionsExposeButtonRoleAndUnavailableOnesGiveHints() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                String[] names = {"Abrir APK", "Analisar", "Build APK",
                    "Decompilar", "Editar Smali", "Assinar APK"};
                int[] icons = {
                    R.drawable.ic_p7_folder, R.drawable.ic_p7_search,
                    R.drawable.ic_p7_wrench, R.drawable.ic_p7_code,
                    R.drawable.ic_p7_file, R.drawable.ic_p7_shield
                };
                int[] count = new int[6];
                android.view.View.OnClickListener[] handlers =
                    new android.view.View.OnClickListener[6];
                for (int i = 0; i < handlers.length; i++) {
                    final int id = i;
                    handlers[i] = v -> count[id]++;
                }
                LinearLayout grid = new LinearLayout(activity);
                grid.setOrientation(LinearLayout.VERTICAL);
                P7ActionGrid.populate(activity, grid, names, icons, handlers,
                    5, 393, 1f, 1f);
                int at = 0;
                for (int rowId = 0; rowId < grid.getChildCount(); rowId++) {
                    LinearLayout row = (LinearLayout) grid.getChildAt(rowId);
                    for (int col = 0; col < row.getChildCount(); col++) {
                        android.view.View tile = row.getChildAt(col);
                        assertEquals(names[at], tile.getContentDescription());
                        assertTrue(tile.isClickable());
                        assertTrue(tile.isFocusable());
                        assertTrue(tile.getMinimumHeight()
                            >= NegrescoTheme.dp(activity, 48));
                        android.view.View.AccessibilityDelegate delegate =
                            tile.getAccessibilityDelegate();
                        assertNotNull("Action must have button semantics", delegate);
                        android.view.accessibility.AccessibilityNodeInfo node =
                            android.view.accessibility.AccessibilityNodeInfo.obtain();
                        try {
                            delegate.onInitializeAccessibilityNodeInfo(tile, node);
                            assertEquals(android.widget.Button.class.getName(),
                                node.getClassName());
                            if (at >= 3) {
                                assertNotNull("Unsupported shortcut needs TalkBack hint",
                                    node.getHintText());
                                assertTrue(node.getHintText().toString().contains(
                                    "ainda não disponível"));
                            } else {
                                assertTrue(node.getHintText() == null ||
                                    node.getHintText().length() == 0);
                            }
                        } finally {
                            node.recycle();
                        }
                        assertTrue(tile.performClick());
                        at++;
                    }
                }
                assertEquals(6, at);
                for (int clicks : count) assertEquals(1, clicks);
            });
        }
    }

    private static void assertRepeatablePreview(Context context, int accent,
            int mode, int surface, boolean glow) {
        P7ThemePreviewView thumbnail = new P7ThemePreviewView(
            context, accent, mode, surface, glow);
        thumbnail.layout(0, 0, 100, 100);
        Bitmap expected = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        Bitmap actual = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        try {
            thumbnail.draw(new Canvas(expected));
            Canvas canvas = new Canvas(actual);
            for (int iteration = 0; iteration < 8; iteration++) {
                actual.eraseColor(android.graphics.Color.TRANSPARENT);
                thumbnail.draw(canvas);
                assertTrue("Visual preview must be deterministic after redraw; mode="
                    + mode + ", surface=" + surface, expected.sameAs(actual));
            }
        } finally {
            expected.recycle();
            actual.recycle();
        }
    }

    @Test public void allThemeLayoutAndPresetPreviewsStayVisuallyStableOnRedraw() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        int[] accents = {0xff29acff, 0xffab42ff, 0xff27c99a, 0xffffa24a};
        for (int surface = 0; surface < 3; surface++)
            for (int accent : accents)
                for (boolean glow : new boolean[]{false, true})
                    assertRepeatablePreview(context, accent, 0, surface, glow);
        for (int layout = 0; layout < P7VisualCatalog.LAYOUT_NAMES.length; layout++)
            assertRepeatablePreview(context, 0xff29acff, 1, layout, false);
        for (int i = 0; i < P7VisualCatalog.PRESET_NAMES.length; i++)
            assertRepeatablePreview(context, accents[i % accents.length], 2, 0, false);
    }

    @Test public void presetGradientIsCachedForEntireViewLifetime()
            throws Exception {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        java.lang.reflect.Field shader = P7ThemePreviewView.class
            .getDeclaredField("presetGradient");
        shader.setAccessible(true);
        P7ThemePreviewView preview = new P7ThemePreviewView(
            context, 0xff29acff, 2, 0, false);
        preview.layout(0, 0, 100, 100);
        Object cached = shader.get(preview);
        assertNotNull("Preset shader should be created exactly once", cached);
        Bitmap bitmap = Bitmap.createBitmap(100, 100, Bitmap.Config.ARGB_8888);
        try {
            Canvas canvas = new Canvas(bitmap);
            for (int pass = 0; pass < 30; pass++) {
                preview.draw(canvas);
                assertSame("Redraw must reuse the same gradient object",
                    cached, shader.get(preview));
            }
            assertNull("Layout does not need a preset gradient",
                shader.get(new P7ThemePreviewView(context, 0xff29acff, 1, 3, false)));
            assertNull("Theme does not need a preset gradient",
                shader.get(new P7ThemePreviewView(context, 0xff29acff, 0, 1, true)));
        } finally {
            bitmap.recycle();
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

    private static void restorePresetPreferences(SharedPreferences prefs,
            java.util.Map<String, ?> before) {
        String[] keys = {"theme", "accent", "studio_glow", "card_radius",
            "layout_variant", "compact", "p7_active_preset"};
        SharedPreferences.Editor restore = prefs.edit();
        for (String key : keys) {
            if (!before.containsKey(key)) {
                restore.remove(key);
            } else {
                Object value = before.get(key);
                if (value instanceof String) restore.putString(key, (String) value);
                else if (value instanceof Boolean) restore.putBoolean(key, (Boolean) value);
                else if (value instanceof Integer) restore.putInt(key, (Integer) value);
                else throw new AssertionError("Unexpected preset field " + key);
            }
        }
        assertTrue(restore.commit());
    }

    @Test public void allFivePresetsRoundTripAgainstTheirWholeAppearanceState() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        java.util.Map<String, ?> before = prefs.getAll();
        try {
            assertEquals(5, P7VisualCatalog.PRESET_NAMES.length);
            for (int index = 0; index < P7VisualCatalog.PRESET_NAMES.length; index++) {
                P7VisualCatalog.persistPreset(context, index);
                assertEquals("Correctly applied preset must remain selected",
                    index, P7VisualCatalog.currentPreset(context));
                assertEquals(index, prefs.getInt("p7_active_preset", -1));
            }
            try {
                P7VisualCatalog.persistPreset(context, 5);
                fail("Missing preset must be rejected without modifying state");
            } catch (IllegalArgumentException expected) {
                assertEquals(4, P7VisualCatalog.currentPreset(context));
            }
        } finally {
            restorePresetPreferences(prefs, before);
        }
    }

    @Test public void manualChangesToAnyPresetSettingClearItsSelection() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        java.util.Map<String, ?> before = prefs.getAll();
        try {
            for (int index = 0; index < P7VisualCatalog.PRESET_NAMES.length; index++) {
                P7VisualCatalog.persistPreset(context, index);
                assertEquals(index, P7VisualCatalog.currentPreset(context));

                String theme = prefs.getString("theme", "");
                assertTrue(prefs.edit().putString("theme",
                    "oled".equals(theme) ? "light" : "oled").commit());
                assertEquals(-1, P7VisualCatalog.currentPreset(context));
                P7VisualCatalog.persistPreset(context, index);

                String accent = prefs.getString("accent", "");
                assertTrue(prefs.edit().putString("accent",
                    "green".equals(accent) ? "purple" : "green").commit());
                assertEquals(-1, P7VisualCatalog.currentPreset(context));
                P7VisualCatalog.persistPreset(context, index);

                assertTrue(prefs.edit().putBoolean("studio_glow",
                    !prefs.getBoolean("studio_glow", true)).commit());
                assertEquals(-1, P7VisualCatalog.currentPreset(context));
                P7VisualCatalog.persistPreset(context, index);

                assertTrue(prefs.edit().putInt("card_radius",
                    prefs.getInt("card_radius", 18) == 12 ? 26 : 12).commit());
                assertEquals(-1, P7VisualCatalog.currentPreset(context));
                P7VisualCatalog.persistPreset(context, index);

                assertTrue(prefs.edit().putInt("layout_variant", 5).commit());
                assertEquals(-1, P7VisualCatalog.currentPreset(context));
                P7VisualCatalog.persistPreset(context, index);

                assertTrue(prefs.edit().putBoolean("compact",
                    !prefs.getBoolean("compact", false)).commit());
                assertEquals(-1, P7VisualCatalog.currentPreset(context));
            }
        } finally {
            restorePresetPreferences(prefs, before);
        }
    }

    @Test public void personalizationColumnPolicyProtectsNarrowAndLargeTextLayouts() {
        assertEquals(2,
            StudioDashboard.personalizationColumnsForViewport(0, 393, 1f, 1f));
        assertEquals(2,
            StudioDashboard.personalizationColumnsForViewport(4, 600, 1f, 1f));
        assertEquals(1,
            StudioDashboard.personalizationColumnsForViewport(0, 359, 1f, 1f));
        assertEquals(1,
            StudioDashboard.personalizationColumnsForViewport(4, 393, 1.25f, 1f));
        assertEquals(1,
            StudioDashboard.personalizationColumnsForViewport(5, 393, 1f, 1.35f));
        assertEquals(1,
            StudioDashboard.personalizationColumnsForViewport(3, 600, 1f, 1f));
        for (int index = 0; index < P7VisualCatalog.LAYOUT_NAMES.length; index++) {
            int normal = StudioDashboard.personalizationColumnsForViewport(
                index, 393, 1f, 1f);
            assertEquals("Only list layout starts in one column",
                index == 3 ? 1 : 2, normal);
            assertEquals(1, StudioDashboard.personalizationColumnsForViewport(
                index, 320, 1.3f, 1.35f));
        }
    }

    @Test public void enlargedFontShowsAllThirteenPersonalizationControlsInOneColumn() {
        Context context = androidx.test.platform.app.InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", Context.MODE_PRIVATE);
        boolean hadFont = prefs.contains("font_percent");
        int oldFont = prefs.getInt("font_percent", 100);
        boolean hadLayout = prefs.contains("layout_variant");
        int oldLayout = prefs.getInt("layout_variant", 0);
        boolean hadCompact = prefs.contains("compact");
        boolean oldCompact = prefs.getBoolean("compact", false);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135)
                .putInt("layout_variant", 0)
                .putBoolean("compact", false).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    LinearLayout settings = activity.getWindow().getDecorView()
                        .findViewWithTag("p7-personalization-options");
                    assertNotNull(settings);
                    assertEquals("All thirteen options must remain visible", 13,
                        settings.getChildCount());
                    for (int i = 0; i < settings.getChildCount(); i++) {
                        LinearLayout row = (LinearLayout) settings.getChildAt(i);
                        assertEquals("Large text requires one option per row", 1,
                            row.getChildCount());
                        android.view.View item = row.getChildAt(0);
                        assertEquals(-1, item.getLayoutParams().width);
                        assertTrue(item.isClickable());
                        assertTrue(item.isFocusable());
                        assertNotNull(item.getContentDescription());
                    }
                    assertEquals("A transient reflow cannot alter the saved layout",
                        0, prefs.getInt("layout_variant", -1));
                });
            }
        } finally {
            SharedPreferences.Editor restore = prefs.edit();
            if (hadFont) restore.putInt("font_percent", oldFont);
            else restore.remove("font_percent");
            if (hadLayout) restore.putInt("layout_variant", oldLayout);
            else restore.remove("layout_variant");
            if (hadCompact) restore.putBoolean("compact", oldCompact);
            else restore.remove("compact");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void thirteenPersonalizationCardsExposeButtonSemanticsForTalkBack() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                LinearLayout settings = activity.getWindow().getDecorView()
                    .findViewWithTag("p7-personalization-options");
                assertNotNull(settings);
                int checked = 0;
                for (int rowIndex = 0; rowIndex < settings.getChildCount(); rowIndex++) {
                    LinearLayout row = (LinearLayout) settings.getChildAt(rowIndex);
                    for (int column = 0; column < row.getChildCount(); column++) {
                        android.view.View option = row.getChildAt(column);
                        assertTrue(option.isClickable());
                        assertTrue(option.isFocusable());
                        assertTrue(option.getMinimumHeight()
                            >= NegrescoTheme.dp(activity, 48));
                        assertNotNull(option.getContentDescription());
                        assertTrue("Each option must announce its name and purpose",
                            option.getContentDescription().toString().contains(". "));
                        android.view.View.AccessibilityDelegate delegate =
                            option.getAccessibilityDelegate();
                        assertNotNull("Personalization card needs a button role", delegate);
                        android.view.accessibility.AccessibilityNodeInfo node =
                            android.view.accessibility.AccessibilityNodeInfo.obtain();
                        try {
                            delegate.onInitializeAccessibilityNodeInfo(option, node);
                            assertEquals(android.widget.Button.class.getName(),
                                node.getClassName());
                            assertTrue(node.isClickable());
                        } finally {
                            node.recycle();
                        }
                        checked++;
                    }
                }
                assertEquals("All thirteen original controls remain accessible",
                    13, checked);
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
