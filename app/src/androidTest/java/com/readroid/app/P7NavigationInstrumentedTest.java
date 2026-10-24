package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import androidx.test.platform.app.InstrumentationRegistry;
import java.lang.reflect.Field;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class P7NavigationInstrumentedTest {
    private static View byDescription(View view,String prefix) {
        CharSequence label=view.getContentDescription();
        if(label!=null && (label.toString().startsWith(prefix)
            || (prefix.startsWith("Abrir seção ") && label.toString()
                .startsWith("Seção " + prefix.substring("Abrir seção ".length()))))
            && view.isClickable())return view;
        if(view instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++) {
                View found=byDescription(group.getChildAt(i),prefix);
                if(found!=null)return found;
            }
        }
        return null;
    }
    /** Informative views carry TalkBack descriptions without being buttons. */
    private static View describedView(View view, String label) {
        CharSequence description = view.getContentDescription();
        if (description != null && description.toString().startsWith(label))
            return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = describedView(group.getChildAt(i), label);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static boolean hasText(View view,String value) {
        if(view instanceof TextView && value.equals(((TextView)view).getText().toString())
            && view.isShown()) return true;
        if(view instanceof ViewGroup) {
            ViewGroup group=(ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++)
                if(hasText(group.getChildAt(i),value))return true;
        }
        return false;
    }
    @Test public void navigationAbbreviationsPreserveFullAccessibleTabNames()
            throws Exception {
        assertEquals("Arquivos",
            MainActivity.navVisualLabel("Arquivos", 393, 1f, 1f));
        assertEquals("Segurança",
            MainActivity.navVisualLabel("Segurança", 393, 1f, 1f));
        assertEquals("Seg.",
            MainActivity.navVisualLabel("Segurança", 320, 1.3f, 1f));
        assertEquals("Arquivos",
            MainActivity.navVisualLabel("Arquivos", 320, 1.3f, 1f));
        assertEquals("Arqs.",
            MainActivity.navVisualLabel("Arquivos", 393, 2f, 1f));
        assertEquals("Seg.",
            MainActivity.navVisualLabel("Segurança", 393, 2f, 1f));
        assertEquals("Início",
            MainActivity.navVisualLabel("Início", 393, 2f, 1f));
        assertEquals("Build",
            MainActivity.navVisualLabel("Build", 393, 2f, 1f));

        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                for (String full : new String[]{
                        "Início", "Arquivos", "Segurança", "Build", "Design"}) {
                    View tab = byDescription(root, "Abrir seção " + full);
                    assertNotNull("Full TalkBack tab name missing: " + full, tab);
                    assertTrue(tab.performClick());
                    assertTrue("Section should announce the full name",
                        tab.getContentDescription().toString()
                            .contains("Seção " + full));
                    assertTrue(tab instanceof ViewGroup);
                    // Marker, icon, then visible non-accessibility TextView.
                    View label = ((ViewGroup) tab).getChildAt(2);
                    assertTrue(label instanceof TextView);
                    assertEquals("Visual tab names must not wrap mid-word",
                        1, ((TextView) label).getMaxLines());
                }
            });
        }
    }

    @Test public void designPagingControlAppearsOnlyWhenAccessibilityTextNeedsScroll()
            throws Exception {
        assertFalse(P7DesignStudio.needsTabPagingControl(393, 1f, 1f));
        assertFalse(P7DesignStudio.needsTabPagingControl(320, 1.3f, 1f));
        assertTrue(P7DesignStudio.needsTabPagingControl(393, 2f, 1f));
        assertTrue(P7DesignStudio.needsTabPagingControl(320, 2f, 1f));
        assertTrue(P7DesignStudio.needsTabPagingControl(393, 1.3f, 1.35f));
        assertFalse(P7DesignStudio.needsTabPagingControl(393, 1f, 1.35f));
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                int width = activity.getResources().getConfiguration().screenWidthDp;
                float font = activity.getResources().getConfiguration().fontScale;
                boolean required = P7DesignStudio.needsTabPagingControl(
                    width, font, NegrescoTheme.FONT_SCALE);
                View pager = byDescription(root,
                    P7DesignStudio.tabPagingLabel(false));
                if (required) {
                    assertNotNull("Large text tab paging button missing", pager);
                    assertTrue(pager.isClickable() && pager.isFocusable());
                    assertTrue(pager.getMinimumWidth() >=
                        NegrescoTheme.dp(activity, 48));
                    assertTrue(pager.getMinimumHeight() >=
                        NegrescoTheme.dp(activity, 48));
                } else {
                    assertNull("Normal Design view must not gain extra chrome", pager);
                }
            });
        }
    }

    @Test public void designPagingTalkBackDescribesNextDestination() {
        assertEquals("Mostrar abas finais do Design Studio",
            P7DesignStudio.tabPagingLabel(false));
        assertEquals("Voltar às primeiras abas do Design Studio",
            P7DesignStudio.tabPagingLabel(true));
        assertNotEquals("Accessible paging actions must differ",
            P7DesignStudio.tabPagingLabel(false),
            P7DesignStudio.tabPagingLabel(true));
    }

    @Test public void designCompactTabsFitFourDestinationsWithoutShrinkingTouchArea() {
        assertTrue(P7DesignStudio.fitsFourTabs(320, 1.3f, 1f));
        assertTrue(P7DesignStudio.fitsFourTabs(320, 1f, 1f));
        assertFalse("Normal-width mockup keeps the full-sized tabs",
            P7DesignStudio.fitsFourTabs(393, 1.3f, 1f));
        assertFalse("200% should scroll instead of shrinking real text",
            P7DesignStudio.fitsFourTabs(320, 2f, 1f));
        assertFalse("Combined accessibility scaling needs scrolling",
            P7DesignStudio.fitsFourTabs(320, 1.3f, 1.35f));
    }

    @Test public void navigationMatchesReferenceAndDesignStudioIsReal() {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(activity->{
                View root=activity.getWindow().getDecorView();
                String[] names={"Início","Arquivos","Segurança","Build","Design"};
                for(String name:names) {
                    View tab=byDescription(root,"Abrir seção "+name);
                    assertNotNull("Missing bottom tab "+name,tab);
                    assertTrue(tab.performClick());
                    assertTrue(tab.isSelected());
                    assertTrue("Reference nav must expose a thin active marker",
                        tab instanceof ViewGroup);
                    assertEquals("Selected tab needs visible blue dash",
                        View.VISIBLE, ((ViewGroup) tab).getChildAt(0).getVisibility());
                }
                assertTrue(hasText(root,"Design Studio"));
                assertTrue(hasText(root,"Previews de Temas"));
                assertTrue(hasText(root,"Opções de Layout"));
                assertTrue(hasText(root,"Presets de Aparência"));
                View dark = byDescription(root,"Negreco Blue, tema aplicado");
                View matrix = byDescription(root,"Matrix Green, selecionar prévia");
                assertNotNull(dark);
                assertNotNull(matrix);
                // Tapping a tile now opens a real confirmation Dialog. This
                // navigation-only test must not leave it open on teardown;
                // p7_design_smoke verifies apply and Android Back rollback.
                assertTrue(matrix.isClickable());
                assertNotNull(byDescription(root,"Abrir seção Início"));
            });
        }
    }

    private static View clickableText(View view, String text) {
        if (view instanceof TextView && text.equals(((TextView) view).getText().toString())
                && view.isClickable()) return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = clickableText(group.getChildAt(i), text);
                if (found != null) return found;
            }
        }
        return null;
    }

    @Test public void designTabsAndCatalogButtonsMeetMinimumTouchTargets()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                int minimum = NegrescoTheme.dp(activity, 48);
                String[] tabs = {"Temas", "Layout", "Ícones", "Logotipo"};
                for (String title : tabs) {
                    View tab = clickableText(root, title);
                    assertNotNull("Missing interactive Design tab " + title, tab);
                    assertTrue("Tab too short: " + title,
                        tab.getLayoutParams().height >= minimum);
                    assertTrue("Tab must be keyboard/TalkBack focusable",
                        tab.isFocusable());
                    assertTrue("Tab minHeight too short: " + title,
                        tab.getMinimumHeight() >= minimum);
                }
                View themes = byDescription(root,
                    "Ver todos: Previews de Temas");
                assertNotNull("Missing theme gallery action", themes);
                assertTrue("Catalog action height below 48 dp",
                    themes.getMinimumHeight() >= minimum);
                assertEquals("Theme gallery parent must not clip hitbox",
                    minimum, ((View) themes.getParent()).getLayoutParams().height);
                assertNotNull(byDescription(root, "Temas, aba selecionada"));
                View icons = clickableText(root, "Ícones");
                assertTrue(icons.performClick());
                assertNotNull(byDescription(root, "Ícones, aba selecionada"));
                assertNotNull(byDescription(root, "Temas, selecionar aba"));
                assertNotNull(byDescription(root, "Logotipo, selecionar aba"));
                View logo = clickableText(root, "Logotipo");
                assertTrue(logo.performClick());
                assertNotNull(byDescription(root, "Logotipo, aba selecionada"));
            });
        }
    }

    private static void assertAccessibleButton(View control) {
        assertNotNull(control);
        assertTrue(control.isClickable());
        assertTrue(control.isFocusable());
        assertNotNull("Clickable text needs explicit button semantics",
            control.getAccessibilityDelegate());
        android.view.accessibility.AccessibilityNodeInfo node =
            android.view.accessibility.AccessibilityNodeInfo.obtain();
        try {
            control.getAccessibilityDelegate()
                .onInitializeAccessibilityNodeInfo(control, node);
            assertEquals(Button.class.getName(), node.getClassName());
            assertTrue(node.isClickable());
            assertEquals(control.isSelected(), node.isSelected());
            assertEquals(control.getContentDescription(), node.getContentDescription());
        } finally {
            node.recycle();
        }
    }

    @Test public void viewAllWaitsForThemeConfirmationAndRecoversAfterCancel() {
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            first = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                assertTrue(byDescription(root, "Abrir seção Design").performClick());
                android.content.SharedPreferences prefs =
                    activity.getSharedPreferences("v3_personalizacao", 0);
                java.util.Map<String, ?> saved =
                    new java.util.HashMap<>(prefs.getAll());
                int current = P7ThemeCatalog.currentTheme(activity);
                String next = P7ThemeCatalog.nameAt(current == 0 ? 1 : 0);
                assertTrue(byDescription(root, next + ",").performClick());
                P7DesignStudio studio;
                try {
                    java.lang.reflect.Field field =
                        MainActivity.class.getDeclaredField("designStudio");
                    field.setAccessible(true);
                    studio = (P7DesignStudio) field.get(activity);
                } catch (ReflectiveOperationException error) {
                    throw new AssertionError(error);
                }
                assertNotNull(studio);
                android.app.AlertDialog confirmation =
                    studio.activeThemeConfirmation();
                first.set(confirmation);
                assertNotNull(confirmation);
                assertTrue(confirmation.isShowing());
                View opener = byDescription(
                    root, "Ver todos: Previews de Temas");
                assertAccessibleButton(opener);
                assertTrue(opener.performClick());
                assertNull("View All may not appear behind Apply confirmation",
                    studio.activeCatalogChooser());
                assertSame(confirmation, studio.activeThemeConfirmation());
                assertEquals(saved, prefs.getAll());
                assertTrue(confirmation.getButton(
                    android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                assertFalse(first.get().isShowing());
                P7DesignStudio studio;
                try {
                    java.lang.reflect.Field field =
                        MainActivity.class.getDeclaredField("designStudio");
                    field.setAccessible(true);
                    studio = (P7DesignStudio) field.get(activity);
                } catch (ReflectiveOperationException error) {
                    throw new AssertionError(error);
                }
                assertNull(studio.activeThemeConfirmation());
                View opener = byDescription(
                    activity.getWindow().getDecorView(),
                    "Ver todos: Previews de Temas");
                assertAccessibleButton(opener);
                assertTrue("View All must work normally after Cancel",
                    opener.performClick());
                android.app.AlertDialog chooser = studio.activeCatalogChooser();
                assertNotNull(chooser);
                assertTrue(chooser.isShowing());
                assertTrue(chooser.getButton(
                    android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
            });
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                android.app.AlertDialog confirmation = first.get();
                if (confirmation != null && confirmation.isShowing())
                    confirmation.cancel();
            });
        }
    }

    @Test public void crossFamilyAppearanceConfirmationsNeverStackOrLeavePhantomPreview() {
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            pending = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    assertTrue(byDescription(root, "Abrir seção Design").performClick());
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    java.util.Map<String, ?> saved =
                        new java.util.HashMap<>(prefs.getAll());
                    P7DesignStudio studio;
                    try {
                        java.lang.reflect.Field f =
                            MainActivity.class.getDeclaredField("designStudio");
                        f.setAccessible(true);
                        studio = (P7DesignStudio) f.get(activity);
                    } catch (ReflectiveOperationException e) {
                        throw new AssertionError("Studio unavailable", e);
                    }
                    assertNotNull(studio);
                    int currentTheme = P7ThemeCatalog.currentTheme(activity);
                    String themeChoice = P7ThemeCatalog.nameAt(
                        currentTheme == 0 ? 1 : 0);
                    String savedTheme = currentTheme < 0 ? null
                        : P7ThemeCatalog.nameAt(currentTheme);
                    int currentLayout = P7VisualCatalog.currentLayout(activity);
                    String layoutChoice = P7VisualCatalog.LAYOUT_NAMES[
                        currentLayout == 0 ? 1 : 0];
                    String savedLayout = P7VisualCatalog.LAYOUT_NAMES[currentLayout];
                    int currentPreset = P7VisualCatalog.currentPreset(activity);
                    String presetChoice = P7VisualCatalog.PRESET_NAMES[
                        currentPreset == 0 ? 1 : 0];
                    String savedPreset = currentPreset < 0 ? null
                        : P7VisualCatalog.PRESET_NAMES[currentPreset];

                    View themeTile = byDescription(root, themeChoice + ",");
                    assertAccessibleButton(themeTile);
                    assertTrue(themeTile.performClick());
                    android.app.AlertDialog themeDialog =
                        studio.activeThemeConfirmation();
                    pending.set(themeDialog);
                    assertNotNull(themeDialog);
                    assertTrue(themeDialog.isShowing());
                    assertTrue(byDescription(root, layoutChoice + ",")
                        .performClick());
                    assertNull("Layout cannot stack behind theme confirmation",
                        studio.activeLayoutConfirmation());
                    assertTrue(themeDialog.isShowing());
                    assertTrue(byDescription(root, presetChoice + ",")
                        .performClick());
                    assertNull("Preset cannot stack behind theme confirmation",
                        studio.activePresetConfirmation());
                    assertTrue(themeDialog.isShowing());
                    assertNotNull(byDescription(root,
                        savedLayout + ", layout aplicado"));
                    if (savedPreset != null)
                        assertNotNull(byDescription(root,
                            savedPreset + ", preset aplicado"));
                    assertEquals("Blocked choices must not persist",
                        saved, prefs.getAll());
                    assertTrue(themeDialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    pending.set(null);
                    if (savedTheme != null)
                        assertNotNull(byDescription(root,
                            savedTheme + ", tema aplicado"));

                    assertTrue(byDescription(root, layoutChoice + ",")
                        .performClick());
                    android.app.AlertDialog layoutDialog =
                        studio.activeLayoutConfirmation();
                    pending.set(layoutDialog);
                    assertNotNull(layoutDialog);
                    assertTrue(layoutDialog.isShowing());
                    assertTrue(byDescription(root, themeChoice + ",")
                        .performClick());
                    assertNull("Theme cannot stack behind layout confirmation",
                        studio.activeThemeConfirmation());
                    assertTrue(byDescription(root, presetChoice + ",")
                        .performClick());
                    assertNull("Preset cannot stack behind layout confirmation",
                        studio.activePresetConfirmation());
                    assertTrue(layoutDialog.isShowing());
                    assertTrue(layoutDialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    pending.set(null);

                    assertTrue(byDescription(root, presetChoice + ",")
                        .performClick());
                    android.app.AlertDialog presetDialog =
                        studio.activePresetConfirmation();
                    pending.set(presetDialog);
                    assertNotNull(presetDialog);
                    assertTrue(presetDialog.isShowing());
                    assertTrue(byDescription(root, themeChoice + ",")
                        .performClick());
                    assertNull("Theme cannot stack behind preset confirmation",
                        studio.activeThemeConfirmation());
                    assertTrue(byDescription(root, layoutChoice + ",")
                        .performClick());
                    assertNull("Layout cannot stack behind preset confirmation",
                        studio.activeLayoutConfirmation());
                    assertTrue(presetDialog.isShowing());
                    assertTrue(presetDialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    pending.set(null);
                    assertEquals("No cross-family tap may save or alter appearance",
                        saved, prefs.getAll());
                    assertNotNull(byDescription(root,
                        savedLayout + ", layout aplicado"));
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = pending.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void catalogSelectionsRequireNativeConfirmationBeforeSaving() {
        final String[] groups = {
            "Previews de Temas", "Opções de Layout", "Presets de Aparência"
        };
        final String[][] choices = {
            P7ThemeCatalog.names(),
            P7VisualCatalog.LAYOUT_NAMES,
            P7VisualCatalog.PRESET_NAMES
        };
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            latest = new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> saved =
                new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    assertTrue(byDescription(activity.getWindow().getDecorView(),
                        "Abrir seção Design").performClick());
                    saved.set(new java.util.HashMap<>(activity
                        .getSharedPreferences("v3_personalizacao", 0).getAll()));
                });
                for (int type = 0; type < groups.length; type++) {
                    final int kind = type;
                    scenario.onActivity(activity -> {
                        View root = activity.getWindow().getDecorView();
                        View opener = byDescription(
                            root, "Ver todos: " + groups[kind]);
                        assertAccessibleButton(opener);
                        assertTrue(opener.performClick());
                        P7DesignStudio studio;
                        try {
                            java.lang.reflect.Field field =
                                MainActivity.class.getDeclaredField("designStudio");
                            field.setAccessible(true);
                            studio = (P7DesignStudio) field.get(activity);
                        } catch (ReflectiveOperationException error) {
                            throw new AssertionError("Studio unavailable", error);
                        }
                        assertNotNull(studio);
                        android.app.AlertDialog chooser = studio.activeCatalogChooser();
                        latest.set(chooser);
                        assertNotNull(chooser);
                        assertTrue(chooser.isShowing());
                        android.widget.ListView list = chooser.getListView();
                        assertNotNull(list);
                        assertEquals("Chooser must expose all catalog options",
                            choices[kind].length, list.getAdapter().getCount());
                        int committed = kind == 0
                            ? P7ThemeCatalog.currentTheme(activity)
                            : kind == 1 ? P7VisualCatalog.currentLayout(activity)
                            : P7VisualCatalog.currentPreset(activity);
                        int alternative = committed == 0 ? 1 : 0;
                        assertTrue("Every catalog must have alternate choices",
                            alternative < choices[kind].length);
                        // The native dialog has just been shown on the main
                        // thread. Its ListView may not have laid out children
                        // yet. performItemClick accepts a null child and still
                        // calls the real AdapterView.OnItemClickListener with
                        // the authentic item ID, without pixel-coordinate guesses.
                        assertTrue("List selection opens an Apply confirmation",
                            list.performItemClick(null, alternative,
                                list.getAdapter().getItemId(alternative)));
                        assertFalse("Choosing item must close native catalog chooser",
                            chooser.isShowing());
                        android.app.AlertDialog confirmation = kind == 0
                            ? studio.activeThemeConfirmation()
                            : kind == 1 ? studio.activeLayoutConfirmation()
                            : studio.activePresetConfirmation();
                        latest.set(confirmation);
                        assertNotNull("Choice opens actual native Apply confirmation",
                            confirmation);
                        assertTrue(confirmation.isShowing());
                        assertNotNull(confirmation.getWindow());
                        String title = kind == 1
                            ? "Aplicar layout " + choices[kind][alternative] + "?"
                            : "Aplicar " + choices[kind][alternative] + "?";
                        assertTrue("Confirmation must match selected catalog option",
                            hasText(confirmation.getWindow().getDecorView(), title));
                        assertEquals("Selecting option cannot persist without Apply",
                            saved.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                        android.widget.Button cancel = confirmation.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE);
                        assertNotNull(cancel);
                        assertEquals("Cancelar", cancel.getText().toString());
                        assertTrue(cancel.performClick());
                    });
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        assertNotNull(latest.get());
                        assertFalse("Cancel must dismiss confirmation",
                            latest.get().isShowing());
                        P7DesignStudio studio;
                        try {
                            java.lang.reflect.Field field =
                                MainActivity.class.getDeclaredField("designStudio");
                            field.setAccessible(true);
                            studio = (P7DesignStudio) field.get(activity);
                        } catch (ReflectiveOperationException error) {
                            throw new AssertionError("Studio unavailable", error);
                        }
                        assertNull("Chooser must release its handle",
                            studio.activeCatalogChooser());
                        assertNull("Theme confirmation must be closed",
                            studio.activeThemeConfirmation());
                        assertNull("Layout confirmation must be closed",
                            studio.activeLayoutConfirmation());
                        assertNull("Preset confirmation must be closed",
                            studio.activePresetConfirmation());
                        assertEquals("Cancel preserves complete appearance state",
                            saved.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                    });
                    latest.set(null);
                }
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = latest.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void repeatedViewAllNeverStacksNativeCatalogChoosers() {
        final String[] sections = {
            "Previews de Temas", "Opções de Layout", "Presets de Aparência"
        };
        final String[] titles = {
            "Temas disponíveis", "Layouts disponíveis", "Presets disponíveis"
        };
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> original =
                new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            opened = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    original.set(new java.util.HashMap<>(activity
                        .getSharedPreferences("v3_personalizacao", 0).getAll()));
                });
                for (int index = 0; index < sections.length; index++) {
                    final int selection = index;
                    scenario.onActivity(activity -> {
                        View root = activity.getWindow().getDecorView();
                        View opener = byDescription(
                            root, "Ver todos: " + sections[selection]);
                        assertAccessibleButton(opener);
                        assertTrue("First View All click opens chooser",
                            opener.performClick());
                        P7DesignStudio studio;
                        try {
                            java.lang.reflect.Field field =
                                MainActivity.class.getDeclaredField("designStudio");
                            field.setAccessible(true);
                            studio = (P7DesignStudio) field.get(activity);
                        } catch (ReflectiveOperationException error) {
                            throw new AssertionError("Cannot inspect Design Studio",
                                error);
                        }
                        assertNotNull(studio);
                        android.app.AlertDialog chooser = studio.activeCatalogChooser();
                        opened.set(chooser);
                        assertNotNull("A real chooser must exist", chooser);
                        assertTrue(chooser.isShowing());
                        assertNotNull(chooser.getWindow());
                        assertTrue("Chooser title must match its actual catalog",
                            hasText(chooser.getWindow().getDecorView(),
                                titles[selection]));
                        assertTrue("Second queued View All click handled",
                            opener.performClick());
                        assertSame("View All cannot stack a second native chooser",
                            chooser, studio.activeCatalogChooser());
                        assertTrue("First chooser must remain visible",
                            chooser.isShowing());
                        assertEquals("Opening a chooser cannot save appearance",
                            original.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                        android.widget.Button close = chooser.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE);
                        assertNotNull(close);
                        assertEquals("Fechar", close.getText().toString());
                        assertTrue("Fechar must be clickable", close.performClick());
                    });
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        assertNotNull(opened.get());
                        assertFalse("Fechar dismisses the active catalog chooser",
                            opened.get().isShowing());
                        try {
                            java.lang.reflect.Field field =
                                MainActivity.class.getDeclaredField("designStudio");
                            field.setAccessible(true);
                            P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                            assertNull("Dismiss must release the chooser handle",
                                studio.activeCatalogChooser());
                        } catch (ReflectiveOperationException error) {
                            throw new AssertionError("Cannot verify chooser cleanup",
                                error);
                        }
                        assertEquals("Closing a chooser cannot save appearance",
                            original.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                    });
                    opened.set(null);
                }
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = opened.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void designSubtabsAndAllCatalogOpenersAnnounceButtonRoles() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                int minimum = NegrescoTheme.dp(activity, 48);
                for (String section : new String[]{
                        "Previews de Temas", "Opções de Layout",
                        "Presets de Aparência"}) {
                    View opener = byDescription(root, "Ver todos: " + section);
                    assertAccessibleButton(opener);
                    assertTrue(opener.getMinimumHeight() >= minimum);
                }
                for (String name : new String[]{
                        "Temas", "Layout", "Ícones", "Logotipo"}) {
                    View tab = clickableText(root, name);
                    assertAccessibleButton(tab);
                    assertTrue(tab.getMinimumHeight() >= minimum);
                    assertTrue("Subtab must respond to user activation",
                        tab.performClick());
                    assertTrue(tab.isSelected());
                    assertAccessibleButton(tab);
                    assertNotNull(byDescription(root, name + ", aba selecionada"));
                }
            });
        }
    }

    private static TextView accessibleHeading(View node, String target) {
        if (node instanceof TextView) {
            TextView text = (TextView) node;
            if (target.equals(text.getText().toString())
                    && text.isAccessibilityHeading()) return text;
        }
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                TextView match = accessibleHeading(group.getChildAt(i), target);
                if (match != null) return match;
            }
        }
        return null;
    }

    @Test public void designStudioHasRealAccessibleHeadingsAcrossAllFourTabs() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                assertNotNull(accessibleHeading(root, "Design Studio"));
                for (String title : new String[]{
                        "Previews de Temas", "Opções de Layout",
                        "Presets de Aparência", "Personalização existente"}) {
                    TextView heading = accessibleHeading(root, title);
                    assertNotNull("Missing heading navigation for " + title, heading);
                    assertFalse("Section headings are not action buttons",
                        heading.isClickable());
                }
                assertTrue(clickableText(root, "Ícones").performClick());
                assertNotNull(accessibleHeading(root, "Criador de Ícones"));
                assertNotNull(accessibleHeading(root, "Modelos de Ícones"));
                assertNotNull(accessibleHeading(root, "Personalização existente"));
                assertTrue(clickableText(root, "Logotipo").performClick());
                assertNotNull(accessibleHeading(root, "Logo Studio"));
                assertNotNull(accessibleHeading(root, "Personalização existente"));
                assertTrue(clickableText(root, "Layout").performClick());
                assertNotNull(accessibleHeading(root, "Opções de Layout"));
            });
        }
    }

    @Test public void homeAndFeatureTitlesExposeTalkBackHeadingNavigation() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                assertNotNull(accessibleHeading(root, "Ações rápidas"));
                assertTrue(byDescription(root, "Abrir seção Segurança").performClick());
                TextView title = accessibleHeading(root, "Segurança");
                assertNotNull("Security section requires TalkBack heading", title);
                assertFalse(title.isClickable());
                assertTrue(byDescription(root, "Abrir seção Build").performClick());
                assertNotNull(accessibleHeading(root, "Construir"));
            });
        }
    }

    @Test public void actionCardsKeepFullLabelsAndNativeButtonRolesOnEveryDesignTab() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                assertTrue(byDescription(root, "Abrir seção Design").performClick());
                int minHeight = NegrescoTheme.dp(activity, 48);
                String[][] cards = {
                    {"Cores e tons", "Exportar aparência", "Importar aparência"},
                    {"Aplicar layout selecionado", "Componentes e navegação",
                        "Bordas dos cartões", "Cores e tons", "Exportar aparência",
                        "Importar aparência"},
                    {"Abrir criador de ícones", "Cores e tons",
                        "Exportar aparência", "Importar aparência"},
                    {"Criar logo PNG", "Editar nome e subtítulo",
                        "Prévia de aparência", "Cores e tons",
                        "Exportar aparência", "Importar aparência"}
                };
                String[] sections = {"Temas", "Layout", "Ícones", "Logotipo"};
                for (int i = 0; i < sections.length; i++) {
                    View tab = clickableText(root, sections[i]);
                    assertNotNull(tab);
                    assertTrue(tab.performClick());
                    for (String card : cards[i]) {
                        View action = byDescription(root, card + ". ");
                        assertNotNull("Missing accessible Design action " + card,
                            action);
                        assertTrue("Design action needs 48dp minimum target",
                            action.getMinimumHeight() >= minHeight);
                        assertAccessibleButton(action);
                        assertTrue(action.getContentDescription().toString()
                            .startsWith(card + ". "));
                    }
                }
            });
        }
    }

    @Test public void catalogHeadingLayoutPolicyHandlesNarrowAndLargeText() {
        assertFalse(P7DesignStudio.needsExpandedSectionHeader(393, 1f, 1f));
        assertFalse(P7DesignStudio.needsExpandedSectionHeader(600, 1f, 1f));
        assertTrue(P7DesignStudio.needsExpandedSectionHeader(359, 1f, 1f));
        assertTrue(P7DesignStudio.needsExpandedSectionHeader(393, 1.25f, 1f));
        assertTrue(P7DesignStudio.needsExpandedSectionHeader(393, 1f, 1.35f));
        assertTrue(P7DesignStudio.needsExpandedSectionHeader(320, 1.25f, 1.35f));
    }

    @Test public void largeTextReflowsAllCatalogHeadingsAndViewAllButtons() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean had = prefs.contains("font_percent");
        int previous = prefs.getInt("font_percent", 100);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> assertTrue(byDescription(
                    activity.getWindow().getDecorView(), "Abrir seção Design")
                    .performClick()));
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    int minTarget = NegrescoTheme.dp(activity, 48);
                    for (String title : new String[]{
                            "Previews de Temas", "Opções de Layout",
                            "Presets de Aparência"}) {
                        View action = byDescription(root, "Ver todos: " + title);
                        assertAccessibleButton(action);
                        LinearLayout row = (LinearLayout) action.getParent();
                        assertEquals("Large fonts require stacked header actions",
                            LinearLayout.VERTICAL, row.getOrientation());
                        assertEquals(-2, row.getLayoutParams().height);
                        assertTrue(row.getMinimumHeight() >= minTarget);
                        TextView heading = (TextView) row.getChildAt(0);
                        assertEquals(title, heading.getText().toString());
                        assertTrue(heading.isAccessibilityHeading());
                        assertFalse(heading.isClickable());
                        assertEquals(-1, heading.getLayoutParams().width);
                        assertEquals("Catalog chooser remains at least 48dp",
                            true, action.getMinimumHeight() >= minTarget);
                        assertTrue(action.getMinimumWidth() >= minTarget);
                        assertTrue("Heading and action need room without overlap",
                            row.getHeight() >= heading.getHeight() + action.getHeight());
                        assertNotNull(heading.getLayout());
                        for (int line = 0; line < heading.getLayout().getLineCount();
                                line++)
                            assertEquals(0, heading.getLayout().getEllipsisCount(line));
                    }
                });
            }
        } finally {
            android.content.SharedPreferences.Editor editor = prefs.edit();
            if (had) editor.putInt("font_percent", previous);
            else editor.remove("font_percent");
            assertTrue(editor.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void studioCardsRespectReadableContrastAcrossAllThemesAndAccents() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadTheme = prefs.contains("theme");
        String previousTheme = prefs.getString("theme", "oled");
        boolean hadAccent = prefs.contains("accent");
        String previousAccent = prefs.getString("accent", "blue");
        boolean hadCustom = prefs.contains("custom_accent");
        String previousCustom = prefs.getString("custom_accent", "#1688FF");
        try {
            for (String theme : new String[]{"oled", "graphite", "light"}) {
                for (String accent : new String[]{
                        "blue", "purple", "green", "orange", "custom"}) {
                    assertTrue(prefs.edit().putString("theme", theme)
                        .putString("accent", accent)
                        .putString("custom_accent", "#FFFFFF").commit());
                    NegrescoTheme.apply(context);
                    int normal = P7DesignStudio.cardFillColor(false);
                    int selected = P7DesignStudio.cardFillColor(true);
                    assertTrue("Normal label must be readable in " + theme + "/" + accent,
                        NegrescoTheme.contrastRatio(NegrescoTheme.TEXT, normal) >= 4.5);
                    assertTrue("Selected label must be readable in " + theme + "/" + accent,
                        NegrescoTheme.contrastRatio(NegrescoTheme.TEXT, selected) >= 4.5);
                    assertTrue("Selected button outline must remain visible",
                        NegrescoTheme.contrastRatio(
                            P7DesignStudio.cardOutlineColor(true), selected) >= 2.8);
                    if ("light".equals(theme)) {
                        assertEquals(NegrescoTheme.SURFACE, normal);
                        assertEquals(NegrescoTheme.TEXT,
                            P7DesignStudio.tabLabelColor(true));
                        assertTrue(NegrescoTheme.contrastRatio(
                            P7DesignStudio.tabLabelColor(true), selected) >= 4.5);
                    } else {
                        assertEquals(0xff10171f, normal);
                        assertEquals(0xff07294b, selected);
                        assertEquals(NegrescoTheme.ACCENT,
                            P7DesignStudio.tabLabelColor(true));
                    }
                }
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadTheme) restore.putString("theme", previousTheme);
            else restore.remove("theme");
            if (hadAccent) restore.putString("accent", previousAccent);
            else restore.remove("accent");
            if (hadCustom) restore.putString("custom_accent", previousCustom);
            else restore.remove("custom_accent");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void lightThemeDesignNavigationUsesReadableRealCardSurfaces() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadTheme = prefs.contains("theme");
        String previousTheme = prefs.getString("theme", "oled");
        try {
            assertTrue(prefs.edit().putString("theme", "light").commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    TextView active = (TextView) clickableText(root, "Temas");
                    TextView inactive = (TextView) clickableText(root, "Layout");
                    assertNotNull(active);
                    assertNotNull(inactive);
                    assertTrue(active.isSelected());
                    assertFalse(inactive.isSelected());
                    assertSame("Both tabs must share one segmented rail",
                        active.getParent(), inactive.getParent());
                    LinearLayout rail = (LinearLayout) active.getParent();
                    android.graphics.drawable.GradientDrawable shared =
                        (android.graphics.drawable.GradientDrawable)
                            rail.getBackground();
                    assertNotNull("Shared rail must define light-mode color",
                        shared.getColor());
                    assertEquals(P7DesignStudio.cardFillColor(false),
                        shared.getColor().getDefaultColor());
                    for (TextView tab : new TextView[]{active, inactive}) {
                        android.graphics.drawable.GradientDrawable surface =
                            (android.graphics.drawable.GradientDrawable)
                                tab.getBackground();
                        assertNotNull(surface.getColor());
                        int expectedFill = tab.isSelected()
                            ? P7DesignStudio.cardFillColor(true)
                            : android.graphics.Color.TRANSPARENT;
                        assertEquals("Inactive segments must not draw cards",
                            expectedFill, surface.getColor().getDefaultColor());
                        int effectiveSurface = tab.isSelected()
                            ? P7DesignStudio.cardFillColor(true)
                            : shared.getColor().getDefaultColor();
                        assertTrue("Text contrast must use the actual rail surface",
                            NegrescoTheme.contrastRatio(
                                tab.getCurrentTextColor(), effectiveSurface) >= 4.5);
                    }
                    assertTrue(inactive.performClick());
                    assertTrue(inactive.isSelected());
                    assertEquals(NegrescoTheme.TEXT, inactive.getCurrentTextColor());
                    assertNotNull(byDescription(root, "Layout, aba selecionada"));
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadTheme) restore.putString("theme", previousTheme);
            else restore.remove("theme");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void allTwentyFourThemesAnnounceActualGlowAndSubtitle() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                assertTrue(byDescription(root, "Abrir seção Design").performClick());
                int selected = P7ThemeCatalog.currentTheme(activity);
                assertEquals(24, P7ThemeCatalog.count());
                for (int i = 0; i < P7ThemeCatalog.count(); i++) {
                    String name = P7ThemeCatalog.nameAt(i);
                    String subtitle = P7ThemeCatalog.subtitleAt(i);
                    View card = byDescription(root, name + ",");
                    assertNotNull("Missing spoken catalog tile " + name, card);
                    assertAccessibleButton(card);
                    String spoken = card.getContentDescription().toString();
                    assertTrue("TalkBack must include the actual theme subtitle",
                        spoken.contains(subtitle));
                    assertEquals("Theme selection state must match current preferences",
                        selected == i, card.isSelected());
                    assertTrue("Theme glow distinction must be explicit",
                        subtitle.startsWith(P7ThemeCatalog.glowAt(i)
                            ? "Neon" : "Sem brilho"));
                }
            });
        }
    }

    @Test public void enlargedTextRetainsCompleteThemeAndPresetLabels() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadFont = prefs.contains("font_percent");
        int previous = prefs.getInt("font_percent", 100);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> assertTrue(byDescription(
                    activity.getWindow().getDecorView(), "Abrir seção Design")
                    .performClick()));
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    for (int i = 0; i < P7ThemeCatalog.count(); i++) {
                        String name = P7ThemeCatalog.nameAt(i);
                        View found = byDescription(root, name + ",");
                        assertNotNull(found);
                        LinearLayout tile = (LinearLayout) found;
                        assertEquals(NegrescoTheme.dp(activity, 144),
                            tile.getLayoutParams().width);
                        TextView title = (TextView) tile.getChildAt(1);
                        TextView subtitle = (TextView) tile.getChildAt(2);
                        assertEquals(name, title.getText().toString());
                        assertEquals(P7ThemeCatalog.subtitleAt(i),
                            subtitle.getText().toString());
                        assertEquals(3, title.getMaxLines());
                        assertEquals(3, subtitle.getMaxLines());
                        assertNull(title.getEllipsize());
                        assertNull(subtitle.getEllipsize());
                    }
                    for (String name : P7VisualCatalog.PRESET_NAMES) {
                        View found = byDescription(root, name + ",");
                        assertNotNull("Missing full preset " + name, found);
                        LinearLayout tile = (LinearLayout) found;
                        assertEquals(NegrescoTheme.dp(activity, 120),
                            tile.getLayoutParams().width);
                        TextView title = (TextView) tile.getChildAt(1);
                        assertEquals(name, title.getText().toString());
                        assertEquals(3, title.getMaxLines());
                        assertNull(title.getEllipsize());
                        assertAccessibleButton(tile);
                    }
                });
            }
        } finally {
            android.content.SharedPreferences.Editor editor = prefs.edit();
            if (hadFont) editor.putInt("font_percent", previous);
            else editor.remove("font_percent");
            assertTrue(editor.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void designSubtabSurvivesRealActivityRecreation() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                View icons = clickableText(root, "Ícones");
                assertNotNull(icons);
                assertTrue(icons.performClick());
                assertNotNull(byDescription(root, "Ícones, aba selecionada"));
                assertTrue(hasText(root, "Criador de Ícones"));
            });
            // ActivityScenario recreates an Android Activity, exercising the
            // real Bundle save/restore path instead of testing a mock field.
            scenario.recreate();
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue("Parent Design tab must stay selected",
                    design.isSelected());
                assertNotNull("Icons subtab lost during activity recreation",
                    byDescription(root, "Ícones, aba selecionada"));
                assertTrue(hasText(root, "Criador de Ícones"));
                View logo = clickableText(root, "Logotipo");
                assertNotNull(logo);
                assertTrue(logo.performClick());
                assertNotNull(byDescription(root, "Logotipo, aba selecionada"));
                assertTrue(hasText(root, "Logo Studio"));
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                assertNotNull("Logo subtab lost during second recreation",
                    byDescription(root, "Logotipo, aba selecionada"));
                assertTrue(hasText(root, "Logo Studio"));
                assertNotNull(byDescription(root, "Temas, selecionar aba"));
                assertNotNull(byDescription(root, "Ícones, selecionar aba"));
            });
        }
    }

    private static HorizontalScrollView tabScroll(View node) {
        if (node instanceof HorizontalScrollView)
            return (HorizontalScrollView) node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                HorizontalScrollView found = tabScroll(group.getChildAt(i));
                if (found != null) return found;
            }
        }
        return null;
    }

    @Test public void narrowDesignKeepsSelectedTabVisible() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                // Real Android widgets in a constrained 240dp content viewport.
                LinearLayout root = new LinearLayout(activity);
                root.setOrientation(LinearLayout.VERTICAL);
                activity.setContentView(root,
                    new ViewGroup.LayoutParams(
                        NegrescoTheme.dp(activity, 240), -1));
                new P7DesignStudio(activity, root, new Button[13], 3);
                assertNotNull(byDescription(root,
                    "Logotipo, aba selecionada"));
            });
            androidx.test.platform.app.InstrumentationRegistry
                .getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                HorizontalScrollView scroll = tabScroll(root);
                View logo = byDescription(root, "Logotipo, aba selecionada");
                assertNotNull(scroll);
                assertNotNull(logo);
                assertTrue("Narrow viewport must require scrolling",
                    scroll.getWidth() < logo.getRight());
                assertTrue("Selected Logo tab clipped at 240dp",
                    logo.getLeft() >= scroll.getScrollX()
                    && logo.getRight() <= scroll.getScrollX() + scroll.getWidth());
                View themes = clickableText(root, "Temas");
                assertNotNull(themes);
                assertTrue(themes.performClick());
            });
            androidx.test.platform.app.InstrumentationRegistry
                .getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                HorizontalScrollView scroll = tabScroll(root);
                assertNotNull(scroll);
                assertEquals("Returning to Themes must expose first tab",
                    0, scroll.getScrollX());
                assertNotNull(byDescription(root, "Temas, aba selecionada"));
                // P7.28's one-pixel rail padding must never keep horizontal
                // scrolling offset after returning to the first destination.
                assertTrue("Themes must remain a full touch action",
                    clickableText(root, "Temas").getMinimumHeight()
                        >= NegrescoTheme.dp(activity, 48));
            });
        }
    }

    @Test public void layoutCardsKeepCompleteNamesAndNativeButtonRoleAtLargeFont() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadFont = prefs.contains("font_percent");
        int previousFont = prefs.getInt("font_percent", 100);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                // Use the same real Activity/Design navigation as users.
                // Replacing MainActivity's window with a synthetic 320dp
                // setContentView fixture was the last logcat event before
                // recurring API35 emulator disappearance (no assertion trace).
                // The 320dp layout is checked independently by compact-smoke.
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull("Native Design section must exist", design);
                    assertTrue(design.performClick());
                    View layoutTab = clickableText(root, "Layout");
                    assertNotNull("Real Layout tab must be clickable", layoutTab);
                    assertTrue(layoutTab.performClick());
                    assertTrue(layoutTab.isSelected());
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    for (String name : P7VisualCatalog.LAYOUT_NAMES) {
                        View card = byDescription(root, name + ",");
                        assertNotNull("Layout option must be present: " + name, card);
                        assertTrue(card.isFocusable());
                        assertTrue(card.isClickable());
                        assertTrue(card instanceof LinearLayout);
                        LinearLayout tile = (LinearLayout) card;
                        assertTrue("Large font needs wider layout cards",
                            card.getLayoutParams().width >= NegrescoTheme.dp(activity, 140));
                        TextView title = (TextView) tile.getChildAt(1);
                        assertEquals(name, title.getText().toString());
                        // Enlarged catalog labels intentionally allow three
                        // lines in all preview families, including layouts.
                        assertEquals(3, title.getMaxLines());
                        assertNull("Layout titles must never be ellipsized",
                            title.getEllipsize());
                        assertNotNull(title.getLayout());
                        for (int line = 0; line < title.getLayout().getLineCount(); line++)
                            assertEquals("Full layout name must remain readable",
                                0, title.getLayout().getEllipsisCount(line));
                        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                            title.getImportantForAccessibility());
                        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS,
                            tile.getChildAt(0).getImportantForAccessibility());
                        View.AccessibilityDelegate delegate =
                            card.getAccessibilityDelegate();
                        assertNotNull(delegate);
                        android.view.accessibility.AccessibilityNodeInfo node =
                            android.view.accessibility.AccessibilityNodeInfo.obtain();
                        try {
                            delegate.onInitializeAccessibilityNodeInfo(card, node);
                            assertEquals(Button.class.getName(), node.getClassName());
                            assertTrue(node.isClickable());
                        } finally {
                            node.recycle();
                        }
                    }
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadFont) restore.putInt("font_percent", previousFont);
            else restore.remove("font_percent");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void repeatedThemeTapNeverStacksOrChangesConfirmedChoice() {
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> saved =
                new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            opened = new java.util.concurrent.atomic.AtomicReference<>();
        final String[] themeName = {null};
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    saved.set(new java.util.HashMap<>(prefs.getAll()));
                    int current = P7ThemeCatalog.currentTheme(activity);
                    int choice = current == 0 ? 1 : 0;
                    String name = P7ThemeCatalog.nameAt(choice);
                    themeName[0] = name;
                    View card = byDescription(root, name + ",");
                    assertAccessibleButton(card);
                    assertTrue("Theme tap opens a real native confirmation",
                        card.performClick());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNotNull(studio);
                        android.app.AlertDialog dialog =
                            studio.activeThemeConfirmation();
                        opened.set(dialog);
                        assertNotNull("Theme confirmation must exist", dialog);
                        assertTrue(dialog.isShowing());
                        String expectedTitle = "Aplicar " + name + "?";
                        assertNotNull("Native dialog must own a real window",
                            dialog.getWindow());
                        assertTrue("Dialog must name exactly the pending theme",
                            hasText(dialog.getWindow().getDecorView(), expectedTitle));
                        assertTrue("Second queued tap still handled",
                            card.performClick());
                        assertSame("No second theme dialog may replace the first",
                            dialog, studio.activeThemeConfirmation());
                        assertTrue("Original theme confirmation remains showing",
                            dialog.isShowing());
                        assertEquals("Unconfirmed theme cannot change any preference",
                            saved.get(), prefs.getAll());
                        android.widget.Button cancel = dialog.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE);
                        assertNotNull(cancel);
                        assertEquals("Cancelar", cancel.getText().toString());
                        assertTrue("Cancelar remains actionable", cancel.performClick());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Could not inspect native theme confirmation", error);
                    }
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull(opened.get());
                    assertFalse("Cancel must close theme dialog",
                        opened.get().isShowing());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNull("Dismiss releases theme dialog reference",
                            studio.activeThemeConfirmation());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Could not verify theme confirmation cleanup", error);
                    }
                    View restored = byDescription(
                        activity.getWindow().getDecorView(), themeName[0] + ",");
                    assertNotNull("Cancelled theme remains in catalog", restored);
                    assertTrue("Cancelled theme must no longer be selected",
                        restored.getContentDescription().toString().startsWith(
                            themeName[0] + ", selecionar prévia"));
                    assertEquals("Cancel cannot save a theme or any other setting",
                        saved.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = opened.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void repeatedLayoutTapNeverStacksNativeConfirmations() {
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> saved =
                new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            opened = new java.util.concurrent.atomic.AtomicReference<>();
        final String[] layoutName = {null};
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    saved.set(new java.util.HashMap<>(prefs.getAll()));
                    int applied = P7VisualCatalog.currentLayout(activity);
                    int choice = applied == 0 ? 1 : 0;
                    String name = P7VisualCatalog.LAYOUT_NAMES[choice];
                    layoutName[0] = name;
                    View card = byDescription(root, name + ",");
                    assertAccessibleButton(card);
                    assertTrue("Layout tap opens native confirmation",
                        card.performClick());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNotNull(studio);
                        android.app.AlertDialog dialog =
                            studio.activeLayoutConfirmation();
                        opened.set(dialog);
                        assertNotNull("Layout confirmation must exist", dialog);
                        assertTrue(dialog.isShowing());
                        assertTrue("Second queued layout click handled",
                            card.performClick());
                        assertSame("Rapid layout taps must preserve one native dialog",
                            dialog, studio.activeLayoutConfirmation());
                        assertTrue("Original layout confirmation still visible",
                            dialog.isShowing());
                        assertEquals("Unconfirmed layout cannot persist preferences",
                            saved.get(), prefs.getAll());
                        android.widget.Button cancel = dialog.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE);
                        assertNotNull(cancel);
                        assertEquals("Cancelar", cancel.getText().toString());
                        assertTrue("Cancelar must be clickable",
                            cancel.performClick());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Cannot inspect real layout confirmation", error);
                    }
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull(opened.get());
                    assertFalse("Cancel must close single layout dialog",
                        opened.get().isShowing());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNull("Dismiss must release layout confirmation handle",
                            studio.activeLayoutConfirmation());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Cannot verify layout dialog cleanup", error);
                    }
                    View restored = byDescription(
                        activity.getWindow().getDecorView(), layoutName[0] + ",");
                    assertNotNull("Cancelled layout stays available", restored);
                    assertTrue("Cancelled layout preview must return to unselected",
                        restored.getContentDescription().toString().startsWith(
                            layoutName[0] + ", selecionar prévia"));
                    assertEquals("Cancelled repeated layout taps cannot save any setting",
                        saved.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = opened.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void repeatedPresetTapNeverStacksNativeConfirmations() {
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> original =
                new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            first = new java.util.concurrent.atomic.AtomicReference<>();
        final int[] choice = {-1};
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    original.set(new java.util.HashMap<>(prefs.getAll()));
                    int applied = P7VisualCatalog.currentPreset(activity);
                    choice[0] = applied == 0 ? 1 : 0;
                    String name = P7VisualCatalog.PRESET_NAMES[choice[0]];
                    View card = byDescription(root, name + ",");
                    assertAccessibleButton(card);
                    assertTrue("First tap opens native confirmation",
                        card.performClick());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNotNull(studio);
                        android.app.AlertDialog dialog =
                            studio.activePresetConfirmation();
                        first.set(dialog);
                        assertNotNull("First tap must create native dialog", dialog);
                        assertTrue(dialog.isShowing());
                        // Dispatch the already-queued click to the original
                        // card instance, simulating two rapid taps before
                        // the modal prevents a second physical touch.
                        assertTrue("Duplicate tap must remain handled",
                            card.performClick());
                        assertSame("No second dialog may replace the first",
                            dialog, studio.activePresetConfirmation());
                        assertTrue("Original confirmation must remain showing",
                            dialog.isShowing());
                        assertEquals("Double-tap must not persist a preset",
                            original.get(), prefs.getAll());
                        android.widget.Button cancel = dialog.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE);
                        assertNotNull(cancel);
                        assertEquals("Cancelar", cancel.getText().toString());
                        assertTrue(cancel.performClick());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Could not inspect the native Studio dialog", error);
                    }
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull(first.get());
                    assertFalse("Cancelar must dismiss the only confirmation",
                        first.get().isShowing());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNull("Dismiss must clear the native dialog handle",
                            studio.activePresetConfirmation());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Could not check confirmation cleanup", error);
                    }
                    String name = P7VisualCatalog.PRESET_NAMES[choice[0]];
                    View restored = byDescription(
                        activity.getWindow().getDecorView(), name + ",");
                    assertNotNull("Preset must remain in the catalog", restored);
                    assertTrue("Cancelled repeated taps must restore state",
                        restored.getContentDescription().toString().startsWith(
                            name + ", selecionar prévia"));
                    assertEquals("No double tap may save unconfirmed preferences",
                        original.get(),
                        activity.getSharedPreferences("v3_personalizacao", 0)
                            .getAll());
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = first.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void negativePresetButtonRestoresPreferencesAndReleasesDialog() {
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> original =
                new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            opened = new java.util.concurrent.atomic.AtomicReference<>();
        final int[] choice = {-1};
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    original.set(new java.util.HashMap<>(prefs.getAll()));
                    int applied = P7VisualCatalog.currentPreset(activity);
                    choice[0] = applied == 0 ? 1 : 0;
                    String name = P7VisualCatalog.PRESET_NAMES[choice[0]];
                    View card = byDescription(root, name + ",");
                    assertAccessibleButton(card);
                    assertTrue("Preset tile must open native confirmation",
                        card.performClick());
                    assertTrue("Pending preset must not claim applied state",
                        byDescription(root, name + ",")
                            .getContentDescription().toString().startsWith(
                                name + ", prévia escolhida, ainda não aplicada"));
                    assertEquals("Choosing is not saving",
                        original.get(), prefs.getAll());

                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNotNull(studio);
                        android.app.AlertDialog dialog =
                            studio.activePresetConfirmation();
                        opened.set(dialog);
                        assertNotNull("Preset must open a real dialog", dialog);
                        assertTrue(dialog.isShowing());
                        android.widget.Button cancel = dialog.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE);
                        assertNotNull("Native Cancelar button must exist", cancel);
                        assertEquals("Cancelar", cancel.getText().toString());
                        assertTrue("Cancel must be actionable", cancel.performClick());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Could not inspect MainActivity Design Studio", error);
                    }
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull("Cancel must follow an opened confirmation",
                        opened.get());
                    assertFalse("Cancelar must dismiss its AlertDialog",
                        opened.get().isShowing());
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                        assertNull("Dismiss must release the dialog reference",
                            studio.activePresetConfirmation());
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError(
                            "Could not inspect Studio after Cancelar", error);
                    }
                    String name = P7VisualCatalog.PRESET_NAMES[choice[0]];
                    View restored = byDescription(
                        activity.getWindow().getDecorView(), name + ",");
                    assertNotNull("Cancelled preset must remain in catalog", restored);
                    String spoken = restored.getContentDescription().toString();
                    assertTrue("Cancelar must restore the previously committed "
                        + "selection, got: " + spoken,
                        spoken.startsWith(name + ", selecionar prévia"));
                    assertEquals("Cancelar must not alter ANY appearance setting",
                        original.get(),
                        activity.getSharedPreferences("v3_personalizacao", 0)
                            .getAll());
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = opened.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void cancellingDifferentPresetRestoresCommittedAppearance() {
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> original =
                new java.util.concurrent.atomic.AtomicReference<>();
        final int[] choice = {-1};
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            confirmation = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                android.content.SharedPreferences prefs =
                    activity.getSharedPreferences("v3_personalizacao", 0);
                original.set(new java.util.HashMap<>(prefs.getAll()));
                int applied = P7VisualCatalog.currentPreset(activity);
                choice[0] = applied == 4 ? 3 : 4;
                String name = P7VisualCatalog.PRESET_NAMES[choice[0]];
                View pending = byDescription(root, name + ",");
                assertAccessibleButton(pending);
                assertTrue("Selecting a different preset must open confirmation",
                    pending.performClick());
                View updated = byDescription(
                    activity.getWindow().getDecorView(), name + ",");
                assertNotNull(updated);
                assertTrue("Pending preset must not claim to be applied",
                    updated.getContentDescription().toString().startsWith(
                        name + ", prévia escolhida, ainda não aplicada"));
                ViewGroup preview = (ViewGroup) ((ViewGroup) updated).getChildAt(0);
                assertEquals("Pending preset must have no committed check mark",
                    1, preview.getChildCount());
                assertEquals("Previewing must not persist any preference",
                    original.get(), prefs.getAll());
            });
            // UiAutomation.getRootInActiveWindow() is null on some
            // headless emulators, even when Android has shown a dialog.
            // Read the actual native AlertDialog via its owning Studio,
            // instead of depending on a secondary accessibility service.
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                try {
                    java.lang.reflect.Field field =
                        MainActivity.class.getDeclaredField("designStudio");
                    field.setAccessible(true);
                    P7DesignStudio studio = (P7DesignStudio) field.get(activity);
                    assertNotNull("MainActivity must own the native Studio", studio);
                    android.app.AlertDialog dialog =
                        studio.activePresetConfirmation();
                    confirmation.set(dialog);
                    assertNotNull("Click must open a real AlertDialog", dialog);
                    assertTrue("Real confirmation must be visible before Back",
                        dialog.isShowing());
                    assertNotNull("Native dialog must have its own window",
                        dialog.getWindow());
                    assertTrue("Native dialog must be attached before Back",
                        dialog.getWindow().getDecorView().isAttachedToWindow());
                    assertEquals("Confirmation must offer Cancelar",
                        "Cancelar", dialog.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE).getText().toString());
                } catch (ReflectiveOperationException error) {
                    throw new AssertionError("Cannot inspect Studio dialog", error);
                }
            });
            // Leave the confirmed native dialog without pressing Apply.
            // Back must trigger the existing cancel listener, then restore
            // the committed state and leave SharedPreferences unchanged.
            InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(
                android.view.KeyEvent.KEYCODE_BACK);
            // AlertDialog cancellation can enqueue its OnCancelListener after
            // the Back key is dispatched. Compare the post-cancel UI only
            // when the main looper has processed that callback and re-render.
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            assertFalse("Back must actually dismiss the native dialog",
                confirmation.get().isShowing());
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                String name = P7VisualCatalog.PRESET_NAMES[choice[0]];
                View restored = byDescription(root, name + ",");
                assertNotNull("Cancel must restore the previously saved state",
                    restored);
                String announced = restored.getContentDescription().toString();
                assertTrue("Back must restore the unselected card; heard: "
                    + announced, announced.startsWith(
                        name + ", selecionar prévia"));
                assertEquals("Cancel must not save a partial preset",
                    original.get(),
                    activity.getSharedPreferences("v3_personalizacao", 0)
                        .getAll());
            });
            } finally {
                // Prevent one failed assertion from leaving a native dialog
                // above the next instrumentation test.
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog opened = confirmation.get();
                    if (opened != null && opened.isShowing()) opened.cancel();
                });
            }
        }
    }

    @Test public void customThemeOpensDesignWithoutFakeAppliedBadge() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs =
            context.getSharedPreferences("v3_personalizacao", 0);
        boolean hadAccent = prefs.contains("accent");
        String originalAccent = prefs.getString("accent", "blue");
        try {
            assertTrue("Custom accent setup must commit",
                prefs.edit().putString("accent", "custom").commit());
            assertEquals("Noncatalog accent has no selected catalog theme",
                -1, P7ThemeCatalog.currentTheme(context));
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue("Custom appearance must be able to open Design",
                        design.performClick());
                    for (int i = 0; i < P7ThemeCatalog.count(); i++) {
                        String name = P7ThemeCatalog.nameAt(i);
                        View card = byDescription(root, name + ", selecionar prévia");
                        assertAccessibleButton(card);
                        assertEquals("Custom theme cannot have an applied check: "
                                + name, 1,
                            ((ViewGroup) ((ViewGroup) card)
                                .getChildAt(0)).getChildCount());
                    }
                    assertEquals("Browsing catalog cannot apply a canned theme",
                        -1, P7ThemeCatalog.currentTheme(activity));
                    assertEquals("Custom accent remains unchanged", "custom",
                        prefs.getString("accent", ""));
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadAccent) restore.putString("accent", originalAccent);
            else restore.remove("accent");
            assertTrue("Restore original custom theme field", restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void themeAndLayoutBadgesRequireCommittedAppearance() {
        assertEquals(", tema aplicado",
            P7DesignStudio.appearanceTileState(0, false, true));
        assertEquals(", layout aplicado",
            P7DesignStudio.appearanceTileState(1, true, true));
        assertEquals(", prévia escolhida, ainda não aplicada",
            P7DesignStudio.appearanceTileState(0, true, false));
        assertEquals(", prévia escolhida, ainda não aplicada",
            P7DesignStudio.appearanceTileState(1, true, false));
        assertEquals(", selecionar prévia",
            P7DesignStudio.appearanceTileState(0, false, false));
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            pending = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertNotNull(design);
                    assertTrue(design.performClick());
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    java.util.Map<String, ?> saved =
                        new java.util.HashMap<>(prefs.getAll());
                    P7DesignStudio studio;
                    try {
                        java.lang.reflect.Field field =
                            MainActivity.class.getDeclaredField("designStudio");
                        field.setAccessible(true);
                        studio = (P7DesignStudio) field.get(activity);
                    } catch (ReflectiveOperationException error) {
                        throw new AssertionError("Studio not inspectable", error);
                    }
                    assertNotNull(studio);
                    int currentTheme = P7ThemeCatalog.currentTheme(activity);
                    String appliedTheme = P7ThemeCatalog.nameAt(currentTheme);
                    String nextTheme = P7ThemeCatalog.nameAt(
                        currentTheme == 0 ? 1 : 0);
                    View committed = byDescription(
                        root, appliedTheme + ", tema aplicado");
                    assertAccessibleButton(committed);
                    assertEquals("Saved theme keeps blue check", 2,
                        ((ViewGroup) ((ViewGroup) committed)
                            .getChildAt(0)).getChildCount());
                    View selectable = byDescription(
                        root, nextTheme + ", selecionar prévia");
                    assertAccessibleButton(selectable);
                    assertTrue(selectable.performClick());
                    android.app.AlertDialog dialog = studio.activeThemeConfirmation();
                    pending.set(dialog);
                    assertNotNull(dialog);
                    assertTrue(dialog.isShowing());
                    View proposed = byDescription(root,
                        nextTheme + ", prévia escolhida, ainda não aplicada");
                    assertAccessibleButton(proposed);
                    assertEquals("Pending theme has no applied badge", 1,
                        ((ViewGroup) ((ViewGroup) proposed)
                            .getChildAt(0)).getChildCount());
                    View prior = byDescription(root, appliedTheme + ", tema aplicado");
                    assertNotNull(prior);
                    assertEquals(2, ((ViewGroup) ((ViewGroup) prior)
                        .getChildAt(0)).getChildCount());
                    assertEquals("No preference changed by preview", saved,
                        prefs.getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    pending.set(null);
                    assertEquals(saved, prefs.getAll());
                    assertNotNull(byDescription(
                        root, appliedTheme + ", tema aplicado"));

                    int currentLayout = P7VisualCatalog.currentLayout(activity);
                    String appliedLayout = P7VisualCatalog.LAYOUT_NAMES[currentLayout];
                    String nextLayout = P7VisualCatalog.LAYOUT_NAMES[
                        currentLayout == 0 ? 1 : 0];
                    committed = byDescription(root, appliedLayout + ", layout aplicado");
                    assertAccessibleButton(committed);
                    assertEquals("Saved layout keeps blue check", 2,
                        ((ViewGroup) ((ViewGroup) committed)
                            .getChildAt(0)).getChildCount());
                    selectable = byDescription(root, nextLayout + ", selecionar prévia");
                    assertAccessibleButton(selectable);
                    assertTrue(selectable.performClick());
                    dialog = studio.activeLayoutConfirmation();
                    pending.set(dialog);
                    assertNotNull(dialog);
                    assertTrue(dialog.isShowing());
                    proposed = byDescription(root,
                        nextLayout + ", prévia escolhida, ainda não aplicada");
                    assertAccessibleButton(proposed);
                    assertEquals("Pending layout has no applied badge", 1,
                        ((ViewGroup) ((ViewGroup) proposed)
                            .getChildAt(0)).getChildCount());
                    prior = byDescription(root, appliedLayout + ", layout aplicado");
                    assertNotNull(prior);
                    assertEquals(2, ((ViewGroup) ((ViewGroup) prior)
                        .getChildAt(0)).getChildCount());
                    assertEquals("No layout saved before Apply", saved,
                        prefs.getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    pending.set(null);
                    assertEquals("Cancel leaves all preferences unchanged",
                        saved, prefs.getAll());
                    assertNotNull(byDescription(
                        root, appliedLayout + ", layout aplicado"));
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = pending.get();
                    if (dialog != null && dialog.isShowing()) dialog.cancel();
                });
            }
        }
    }

    @Test public void presetAppliedIndicatorTracksCommittedValuesOnly() {
        assertEquals(", preset aplicado", P7DesignStudio.presetTileState(true, true));
        assertEquals(", preset aplicado", P7DesignStudio.presetTileState(false, true));
        assertEquals(", prévia escolhida, ainda não aplicada",
            P7DesignStudio.presetTileState(true, false));
        assertEquals(", selecionar prévia",
            P7DesignStudio.presetTileState(false, false));
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                int applied = P7VisualCatalog.currentPreset(activity);
                for (int i = 0; i < P7VisualCatalog.PRESET_NAMES.length; i++) {
                    String name = P7VisualCatalog.PRESET_NAMES[i];
                    View tile = byDescription(root, name + ",");
                    assertAccessibleButton(tile);
                    boolean committed = applied == i;
                    assertTrue(tile.getContentDescription().toString().startsWith(
                        name + (committed ? ", preset aplicado" : ", selecionar prévia")));
                    assertTrue(tile.getContentDescription().toString().contains(
                        P7VisualCatalog.presetSummary(i)));
                    assertTrue(tile instanceof ViewGroup);
                    View preview = ((ViewGroup) tile).getChildAt(0);
                    assertTrue(preview instanceof ViewGroup);
                    assertEquals("Only a committed preset gets the check badge",
                        committed ? 2 : 1,
                        ((ViewGroup) preview).getChildCount());
                }
            });
        }
    }

    @Test public void presetCardsExplainSavedSettingsAsOneAccessibleAction() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                for (int i = 0; i < P7VisualCatalog.PRESET_NAMES.length; i++) {
                    String name = P7VisualCatalog.PRESET_NAMES[i];
                    View tile = byDescription(root, name + ",");
                    assertNotNull("Preset must remain a real button: " + name, tile);
                    assertAccessibleButton(tile);
                    String spoken = tile.getContentDescription().toString();
                    assertTrue("Preset must speak exact saved choices: " + name,
                        spoken.contains(P7VisualCatalog.presetSummary(i)));
                    assertTrue(spoken.startsWith(name + ","));
                }
            });
        }
    }

    @Test public void designTabGlyphsAppearOnlyWhenLabelsHaveRoom() {
        assertTrue("Normal viewport can show four graphic labels",
            P7DesignStudio.showTabGlyphs(393, 1f, 1f));
        assertFalse("320dp must keep all four labels without icons",
            P7DesignStudio.showTabGlyphs(320, 1f, 1f));
        assertFalse("Compact 130 percent must not steal label width",
            P7DesignStudio.showTabGlyphs(320, 1.3f, 1f));
        assertFalse("200 percent must keep complete text and paging",
            P7DesignStudio.showTabGlyphs(393, 2f, 1f));
        assertFalse("Increased app font also needs icon-free labels",
            P7DesignStudio.showTabGlyphs(393, 1f, 1.35f));
    }

    @Test public void designTabsShareOneRailWithoutGapsOrLostActions() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());
                View themes = byDescription(root, "Temas, aba selecionada");
                assertNotNull("Selected Design tab missing", themes);
                assertTrue(themes.getParent() instanceof LinearLayout);
                LinearLayout rail = (LinearLayout) themes.getParent();
                assertEquals("p7-design-segmented-tabs", rail.getTag());
                assertTrue("Segmented rail must have one shared background",
                    rail.getBackground() instanceof
                        android.graphics.drawable.GradientDrawable);
                assertEquals("All four Design tabs must remain accessible",
                    4, rail.getChildCount());
                String[] names = {"Temas", "Layout", "Ícones", "Logotipo"};
                for (int i = 0; i < rail.getChildCount(); i++) {
                    View entry = rail.getChildAt(i);
                    assertTrue(entry instanceof TextView);
                    assertEquals(names[i], ((TextView) entry).getText().toString());
                    assertTrue(entry.isClickable() && entry.isFocusable());
                    assertTrue(entry.getMinimumHeight()
                        >= NegrescoTheme.dp(activity, 48));
                    assertEquals("No floating-card gap inside a segmented rail",
                        0, ((LinearLayout.LayoutParams)
                            entry.getLayoutParams()).rightMargin);
                    assertEquals("Only the first tab starts selected",
                        i == 0, entry.isSelected());
                    assertTrue(entry.getBackground() instanceof
                        android.graphics.drawable.GradientDrawable);
                    TextView label = (TextView) entry;
                    boolean glyphExpected = P7DesignStudio.showTabGlyphs(
                        activity.getResources().getConfiguration().screenWidthDp,
                        activity.getResources().getConfiguration().fontScale,
                        NegrescoTheme.FONT_SCALE);
                    android.graphics.drawable.Drawable glyph =
                        label.getCompoundDrawablesRelative()[0];
                    if (glyphExpected) {
                        assertNotNull("Normal Design tabs need vector symbols",
                            glyph);
                        assertTrue("Only decorative vector, no extra child",
                            glyph.getIntrinsicWidth() > 0);
                        assertEquals("Icon must share the tab's accessible label",
                            names[i] + (i == 0
                                ? ", aba selecionada" : ", selecionar aba"),
                            label.getContentDescription().toString());
                    } else {
                        assertNull("Compact or enlarged labels stay icon-free",
                            glyph);
                    }
                    android.graphics.drawable.GradientDrawable fill =
                        (android.graphics.drawable.GradientDrawable)
                            entry.getBackground();
                    assertNotNull(fill.getColor());
                    if (i > 0) assertEquals(
                        "Inactive tabs must share their parent surface",
                        android.graphics.Color.TRANSPARENT,
                        fill.getColor().getDefaultColor());
                }
                View layout = rail.getChildAt(1);
                assertTrue("Layout must remain a working tab", layout.performClick());
                assertTrue(layout.isSelected());
                TextView layoutText = (TextView) layout;
                assertNotNull("Selected color must also tint its icon",
                    layoutText.getCompoundDrawableTintList());
                assertEquals(layoutText.getCurrentTextColor(),
                    layoutText.getCompoundDrawableTintList().getDefaultColor());
                assertFalse(themes.isSelected());
                assertEquals("Layout, aba selecionada",
                    layout.getContentDescription().toString());
                assertTrue(rail.getChildAt(2).performClick());
                assertTrue(rail.getChildAt(2).isSelected());
                assertTrue(rail.getChildAt(3).performClick());
                assertTrue(rail.getChildAt(3).isSelected());
                assertTrue(themes.performClick());
                assertTrue(themes.isSelected());
            });
        }
    }

    @Test public void creatorCardsUseRealVectorArtworkInsteadOfTextSymbols() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View design = byDescription(root, "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.performClick());

                View iconCard = byDescription(root, "Criador de Ícones: ");
                View logoCard = byDescription(root, "Logo Studio: ");
                assertNotNull("Icon Creator action missing", iconCard);
                assertNotNull("Logo Studio action missing", logoCard);
                assertTrue(iconCard.isClickable());
                assertTrue(logoCard.isClickable());

                int[] expected = {
                    R.drawable.ic_p7_icon_creator,
                    R.drawable.ic_p7_logo_studio_monogram
                };
                View[] cards = {iconCard, logoCard};
                assertNotEquals("The creative card cannot reuse the launcher shield",
                    R.drawable.ic_negrecodroid_foreground, expected[1]);
                for (int i = 0; i < cards.length; i++) {
                    assertTrue("Creator action must be a native layout",
                        cards[i] instanceof LinearLayout);
                    View glyph = ((LinearLayout) cards[i]).getChildAt(0);
                    assertTrue("Creator cannot use plain Unicode text artwork",
                        glyph instanceof android.widget.ImageView);
                    android.widget.ImageView vector =
                        (android.widget.ImageView) glyph;
                    assertEquals("Wrong vector associated with creator action",
                        expected[i], ((Integer) vector.getTag()).intValue());
                    assertNotNull("Vector drawable must actually load",
                        vector.getDrawable());
                    assertTrue(vector.getDrawable().getIntrinsicWidth() > 0);
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                        vector.getImportantForAccessibility());
                    assertEquals(NegrescoTheme.dp(activity, 42),
                        vector.getLayoutParams().width);
                    assertEquals(NegrescoTheme.dp(activity, 42),
                        vector.getLayoutParams().height);
                    assertTrue(cards[i].getContentDescription().toString()
                        .contains(i == 0 ? "Criador de Ícones" : "Logo Studio"));
                    LinearLayout creator = (LinearLayout) cards[i];
                    assertEquals("Creator card needs emblem, text and arrow",
                        3, creator.getChildCount());
                    View arrow = creator.getChildAt(2);
                    assertTrue("Reference arrow must be a vector image",
                        arrow instanceof android.widget.ImageView);
                    android.widget.ImageView arrowImage =
                        (android.widget.ImageView) arrow;
                    assertEquals("p7-creator-action-arrow", arrow.getTag());
                    assertNotNull("Circular arrow drawable must load",
                        arrowImage.getDrawable());
                    assertTrue(arrowImage.getDrawable().getIntrinsicWidth() > 0);
                    assertEquals(NegrescoTheme.dp(activity, 22),
                        arrow.getLayoutParams().width);
                    assertEquals(NegrescoTheme.dp(activity, 22),
                        arrow.getLayoutParams().height);
                    assertEquals(android.view.Gravity.BOTTOM,
                        ((LinearLayout.LayoutParams) arrow.getLayoutParams()).gravity);
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                        arrow.getImportantForAccessibility());
                    assertFalse("Arrow is decoration, never an action",
                        arrow.isClickable());
                    assertFalse("Arrow must not duplicate TalkBack focus",
                        arrow.isFocusable());
                    assertTrue("Only the creator card should open its editor",
                        cards[i].hasOnClickListeners());
                }
            });
        }
    }

    @Test public void enlargedFontsStackCreatorCardsWithoutLosingActions() {
        assertFalse(P7DesignStudio.shouldStackCreators(393, 1f, 1f));
        assertTrue(P7DesignStudio.shouldStackCreators(320, 1f, 1f));
        assertTrue(P7DesignStudio.shouldStackCreators(393, 1.25f, 1f));
        assertTrue(P7DesignStudio.shouldStackCreators(393, 1f, 1.35f));

        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadFont = prefs.contains("font_percent");
        int previous = prefs.getInt("font_percent", 100);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> assertTrue(byDescription(
                    activity.getWindow().getDecorView(), "Abrir seção Design")
                    .performClick()));
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View first = byDescription(root, "Criador de Ícones: ");
                    View second = byDescription(root, "Logo Studio: ");
                    assertNotNull(first);
                    assertNotNull(second);
                    assertTrue(first.isFocusable() && first.isClickable());
                    assertTrue(second.isFocusable() && second.isClickable());
                    assertSame("Both actions belong to the same row",
                        first.getParent(), second.getParent());
                    LinearLayout row = (LinearLayout) first.getParent();
                    assertEquals("Large text must stack creative actions",
                        LinearLayout.VERTICAL, row.getOrientation());
                    for (View card : new View[]{first, second}) {
                        assertEquals(-1, card.getLayoutParams().width);
                        assertEquals(-2, card.getLayoutParams().height);
                        assertTrue(card.getMinimumHeight()
                            >= NegrescoTheme.dp(activity, 88));
                        View.AccessibilityDelegate delegate =
                            card.getAccessibilityDelegate();
                        assertNotNull(delegate);
                        android.view.accessibility.AccessibilityNodeInfo node =
                            android.view.accessibility.AccessibilityNodeInfo.obtain();
                        try {
                            delegate.onInitializeAccessibilityNodeInfo(card, node);
                            assertEquals(Button.class.getName(), node.getClassName());
                            assertTrue(node.isClickable());
                        } finally {
                            node.recycle();
                        }
                    }
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadFont) restore.putInt("font_percent", previous);
            else restore.remove("font_percent");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void logoStudioShowsSavedBrandInsteadOfAFakeExample() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View window = activity.getWindow().getDecorView();
                String saved = activity.getSharedPreferences(
                    "v3_personalizacao", android.content.Context.MODE_PRIVATE)
                    .getString("display_name", "NegrecoDroid");
                assertTrue(byDescription(window, "Abrir seção Design").performClick());
                View logoTab = clickableText(window, "Logotipo");
                assertNotNull("Logo Studio must be a real selectable tab", logoTab);
                assertTrue(logoTab.performClick());
                assertTrue(hasText(window, "Logo Studio"));
                assertTrue("The user-saved brand must be shown in its preview",
                    hasText(window, saved));
                View preview = describedView(window,
                    "Prévia da identidade visual atual. Nome: ");
                assertNotNull("A prévia precisa ser acessível ao TalkBack", preview);
                assertTrue("Spoken preview must contain the saved name",
                    preview.getContentDescription().toString().contains("Nome: " + saved));
            });
        }
    }

    @Test public void logoPreviewAnnouncesSavedNameAndSubtitleWithoutDuplicateNodes() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadName = prefs.contains("display_name");
        String previousName = prefs.getString("display_name", "NegrecoDroid");
        boolean hadSubtitle = prefs.contains("display_subtitle");
        String previousSubtitle = prefs.getString(
            "display_subtitle", "APK ENGINEERING STUDIO");
        boolean hadFont = prefs.contains("font_percent");
        int previousFont = prefs.getInt("font_percent", 100);
        String testName = "NegrecoDroid Laboratório Mobile";
        String testSubtitle = "Análise e personalização de aplicativos Android";
        try {
            assertTrue(prefs.edit().putString("display_name", testName)
                .putString("display_subtitle", testSubtitle)
                .putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    assertTrue(byDescription(root, "Abrir seção Design").performClick());
                    View tab = clickableText(root, "Logotipo");
                    assertNotNull(tab);
                    assertTrue(tab.performClick());
                    View preview = describedView(root,
                        "Prévia da identidade visual atual. Nome: ");
                    assertNotNull(preview);
                    assertEquals("Prévia da identidade visual atual. Nome: "
                        + testName + ". Subtítulo: " + testSubtitle,
                        preview.getContentDescription().toString());
                    assertFalse("Identity preview is information, not a button",
                        preview.isClickable());
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_YES,
                        preview.getImportantForAccessibility());
                    LinearLayout row = (LinearLayout) preview;
                    LinearLayout names = (LinearLayout) row.getChildAt(1);
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS,
                        names.getImportantForAccessibility());
                    TextView brand = (TextView) names.getChildAt(0);
                    TextView subtitle = (TextView) names.getChildAt(1);
                    assertEquals(testName, brand.getText().toString());
                    assertEquals(testSubtitle, subtitle.getText().toString());
                    assertEquals(Integer.MAX_VALUE, brand.getMaxLines());
                    assertEquals(Integer.MAX_VALUE, subtitle.getMaxLines());
                    assertEquals(-2, names.getLayoutParams().height);
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadName) restore.putString("display_name", previousName);
            else restore.remove("display_name");
            if (hadSubtitle) restore.putString("display_subtitle", previousSubtitle);
            else restore.remove("display_subtitle");
            if (hadFont) restore.putInt("font_percent", previousFont);
            else restore.remove("font_percent");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void homeQuickActionsAndRecentHistoryLinkMeet48dpContract() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                int min = NegrescoTheme.dp(activity, 48);
                for (String name : new String[]{"Abrir APK", "Analisar",
                        "Build APK", "Decompilar", "Editar Smali",
                        "Assinar APK"}) {
                    View tile = byDescription(root, name);
                    assertNotNull("Quick action not found: " + name, tile);
                    assertTrue("Quick action shorter than 48dp: " + name,
                        tile.getMinimumHeight() >= min);
                    assertTrue("Quick action must support TalkBack: " + name,
                        tile.isClickable() && tile.isFocusable());
                }
                // Recent-project history is legitimately absent on a fresh
                // install. The history-link hitbox is tested with a real
                // visible synthetic history item in P7HomeOverviewInstrumentedTest.
            });
        }
    }

    @Test public void smaliShortcutDoesNotPretendToOpenAnUnsupportedEditor() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View home = byDescription(root, "Abrir seção Início");
                View files = byDescription(root, "Abrir seção Arquivos");
                View smali = byDescription(root, "Editar Smali");
                assertNotNull(home);
                assertNotNull(files);
                assertNotNull("Smali shortcut is missing", smali);
                assertTrue("The shortcut must open real capability guidance",
                    smali.performClick());
                assertTrue("Unsupported Smali editing must not silently "
                    + "navigate away", home.isSelected());
                assertFalse("The file explorer is not a Smali editor",
                    files.isSelected());
            });
        }
    }

    private static View sectionView(MainActivity activity, String fieldName) {
        try {
            Field field = MainActivity.class.getDeclaredField(fieldName);
            field.setAccessible(true);
            return (View) field.get(activity);
        } catch (Exception error) {
            throw new AssertionError("Missing P7 view: " + fieldName, error);
        }
    }

    private static ScrollView mainScroll(MainActivity activity) {
        return (ScrollView) sectionView(activity, "contentScroll");
    }

    @Test public void bottomTabsKeepIndependentScrollPositionsAndReselectResets() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            // Extra height lives only in the test Activity, not production UI.
            scenario.onActivity(activity -> {
                for (String name : new String[]{"homeSection", "designSection"}) {
                    LinearLayout section = (LinearLayout) sectionView(activity, name);
                    section.addView(new View(activity),
                        new LinearLayout.LayoutParams(1,
                            NegrescoTheme.dp(activity, 1500)));
                }
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            final int[] offsets = new int[2];
            scenario.onActivity(activity -> {
                ScrollView scroll = mainScroll(activity);
                scroll.scrollTo(0, NegrescoTheme.dp(activity, 130));
                offsets[0] = scroll.getScrollY();
                assertTrue("Home fixture must support scrolling", offsets[0] > 0);
                assertTrue(byDescription(activity.getWindow().getDecorView(),
                    "Abrir seção Design").performClick());
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                ScrollView scroll = mainScroll(activity);
                assertEquals("First visit must start at the Design top", 0,
                    scroll.getScrollY());
                scroll.scrollTo(0, NegrescoTheme.dp(activity, 225));
                offsets[1] = scroll.getScrollY();
                assertTrue("Design fixture must support scrolling", offsets[1] > 0);
                assertTrue(byDescription(activity.getWindow().getDecorView(),
                    "Abrir seção Início").performClick());
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                assertEquals("Home position lost while visiting Design",
                    offsets[0], mainScroll(activity).getScrollY());
                assertTrue(byDescription(activity.getWindow().getDecorView(),
                    "Abrir seção Design").performClick());
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                assertEquals("Design position lost while visiting Home",
                    offsets[1], mainScroll(activity).getScrollY());
                assertTrue(byDescription(activity.getWindow().getDecorView(),
                    "Abrir seção Design").performClick());
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> assertEquals(
                "Reselecting active Design must scroll to top",
                0, mainScroll(activity).getScrollY()));
        }
    }

    @Test public void selectedSectionScrollSurvivesActivityRecreation() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> assertTrue(
                byDescription(activity.getWindow().getDecorView(),
                    "Abrir seção Design").performClick()));
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            final int[] previous = new int[1];
            scenario.onActivity(activity -> {
                ScrollView scroll = mainScroll(activity);
                int maxY = Math.max(0, scroll.getChildAt(0).getHeight()
                    - scroll.getHeight());
                assertTrue("Real Design page should scroll on the emulator",
                    maxY >= NegrescoTheme.dp(activity, 40));
                scroll.scrollTo(0, Math.min(NegrescoTheme.dp(activity, 105), maxY));
                previous[0] = scroll.getScrollY();
                assertTrue(previous[0] > 0);
            });
            scenario.recreate();
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                ScrollView scroll = mainScroll(activity);
                assertEquals("Recreated Design page lost reading position",
                    previous[0], scroll.getScrollY());
                View design = byDescription(activity.getWindow().getDecorView(),
                    "Abrir seção Design");
                assertNotNull(design);
                assertTrue(design.isSelected());
            });
        }
    }

    @Test public void homeHeaderOpensActualMenuAndDesignPreferences() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View menu = byDescription(root, "Abrir menu de navegação");
                View settings = byDescription(root, "Abrir personalização");
                assertNotNull("Approved hamburger control is missing", menu);
                assertNotNull("Approved settings gear is missing", settings);
                int minimum = NegrescoTheme.dp(activity, 48);
                for (View target : new View[]{menu, settings}) {
                    assertTrue("Reference toolbar must preserve 22dp glyphs",
                        target.getPaddingLeft() == NegrescoTheme.dp(activity, 13)
                        && target.getPaddingRight() == NegrescoTheme.dp(activity, 13));
                    assertTrue("Toolbar should use a touch ripple, not a big frame",
                        target.getBackground() instanceof
                            android.graphics.drawable.RippleDrawable);
                    assertTrue("Home toolbar target too narrow",
                        target.getLayoutParams().width >= minimum);
                    assertTrue("Home toolbar target too short",
                        target.getLayoutParams().height >= minimum);
                    assertTrue("Home toolbar minimum width missing",
                        target.getMinimumWidth() >= minimum);
                    assertTrue("Home toolbar minimum height missing",
                        target.getMinimumHeight() >= minimum);
                    assertTrue("Home toolbar target must be accessible",
                        target.isFocusable());
                }
                assertTrue("Menu must be a working control", menu.isClickable());
                assertTrue("Settings must be a working control",
                    settings.performClick());
                assertTrue("Settings must open the actual Design Studio",
                    hasText(root, "Design Studio"));
                View home = byDescription(root, "Abrir seção Início");
                assertNotNull(home);
                assertTrue(home.performClick());
                assertTrue("Menu must return with Home", menu.isShown());
                assertTrue(menu.performClick());
            });
        }
    }

}
