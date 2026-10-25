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
    static View byDescription(View view,String prefix) {
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
    static View describedView(View view, String label) {
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

    static View clickableText(View view, String text) {
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

    static void assertAccessibleButton(View control) {
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

    /** Real Activity-owned dialog, not a detached synthetic mock. */
    private static P7DesignStudio studioForModalRegression(MainActivity activity) {
        try {
            java.lang.reflect.Field field =
                MainActivity.class.getDeclaredField("designStudio");
            field.setAccessible(true);
            P7DesignStudio studio = (P7DesignStudio) field.get(activity);
            assertNotNull("Activity must retain its Design Studio", studio);
            return studio;
        } catch (ReflectiveOperationException error) {
            throw new AssertionError("Cannot inspect real Design Studio", error);
        }
    }

    /**
     * Ver todos cannot appear behind an Apply confirmation for Layout/Preset.
     * The exact same native confirmation must survive all queued taps, and
     * after Cancel every chooser must be available without saving settings.
     */
    private static void assertViewAllBlockedByNonThemeConfirmation(int kind) {
        final String[] sections = {
            "Previews de Temas", "Opções de Layout", "Presets de Aparência"
        };
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            confirmationRef = new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<java.util.Map<String, ?>>
            original = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    assertTrue(byDescription(root, "Abrir seção Design").performClick());
                    P7DesignStudio studio = studioForModalRegression(activity);
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    original.set(new java.util.HashMap<>(prefs.getAll()));

                    int committed = kind == 1
                        ? P7VisualCatalog.currentLayout(activity)
                        : P7VisualCatalog.currentPreset(activity);
                    String[] options = kind == 1
                        ? P7VisualCatalog.LAYOUT_NAMES
                        : P7VisualCatalog.PRESET_NAMES;
                    int alternative = committed == 0 ? 1 : 0;
                    assertTrue("Catalog must contain another choice",
                        alternative < options.length);
                    View tile = byDescription(root, options[alternative] + ",");
                    assertAccessibleButton(tile);
                    assertTrue("Selecting a preview opens native confirmation",
                        tile.performClick());

                    android.app.AlertDialog confirmation = kind == 1
                        ? studio.activeLayoutConfirmation()
                        : studio.activePresetConfirmation();
                    confirmationRef.set(confirmation);
                    assertNotNull("A real Apply confirmation must be showing",
                        confirmation);
                    assertTrue(confirmation.isShowing());
                    assertNull(studio.activeCatalogChooser());

                    for (String section : sections) {
                        View opener = byDescription(root, "Ver todos: " + section);
                        assertAccessibleButton(opener);
                        assertTrue("Queued View All tap must be handled",
                            opener.performClick());
                        assertNull("View All cannot stack behind Layout/Preset Apply",
                            studio.activeCatalogChooser());
                        assertSame("View All cannot replace the current confirmation",
                            confirmation,
                            kind == 1 ? studio.activeLayoutConfirmation()
                                : studio.activePresetConfirmation());
                        assertTrue(confirmation.isShowing());
                        assertEquals("Blocked catalog taps cannot persist appearance",
                            original.get(), prefs.getAll());
                    }
                    assertEquals("Cancelar",
                        confirmation.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE).getText().toString());
                    assertTrue(confirmation.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                });
                // AlertDialog OnDismiss runs asynchronously on the main looper.
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull(confirmationRef.get());
                    assertFalse("Cancel must dismiss the Apply confirmation",
                        confirmationRef.get().isShowing());
                    P7DesignStudio studio = studioForModalRegression(activity);
                    assertNull("Layout confirmation must release its handle",
                        studio.activeLayoutConfirmation());
                    assertNull("Preset confirmation must release its handle",
                        studio.activePresetConfirmation());
                    assertNull(studio.activeCatalogChooser());
                    assertEquals(original.get(), activity.getSharedPreferences(
                        "v3_personalizacao", 0).getAll());
                });
                for (String section : sections) {
                    scenario.onActivity(activity -> {
                        View opener = byDescription(
                            activity.getWindow().getDecorView(),
                            "Ver todos: " + section);
                        assertAccessibleButton(opener);
                        assertTrue("Chooser works after Cancel", opener.performClick());
                        P7DesignStudio studio = studioForModalRegression(activity);
                        android.app.AlertDialog chooser = studio.activeCatalogChooser();
                        confirmationRef.set(chooser);
                        assertNotNull(chooser);
                        assertTrue(chooser.isShowing());
                        assertNull(studio.activeThemeConfirmation());
                        assertNull(studio.activeLayoutConfirmation());
                        assertNull(studio.activePresetConfirmation());
                        assertEquals("Catalog never persisted unconfirmed options",
                            original.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                        assertTrue(chooser.getButton(
                            android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    });
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        P7DesignStudio studio = studioForModalRegression(activity);
                        assertNotNull(confirmationRef.get());
                        assertFalse(confirmationRef.get().isShowing());
                        assertNull("Fechar must release the native chooser",
                            studio.activeCatalogChooser());
                        assertEquals(original.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    });
                }
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog opened = confirmationRef.get();
                    if (opened != null && opened.isShowing()) opened.cancel();
                });
            }
        }
    }

    @Test public void viewAllWaitsForLayoutConfirmationAndRecoversAfterCancel() {
        assertViewAllBlockedByNonThemeConfirmation(1);
    }

    @Test public void viewAllWaitsForPresetConfirmationAndRecoversAfterCancel() {
        assertViewAllBlockedByNonThemeConfirmation(2);
    }

    @Test public void crossFamilyAppearanceConfirmationsNeverStackOrLeavePhantomPreview() {
        final java.util.concurrent.atomic.AtomicReference<java.util.Map<String, ?>>
            original = new java.util.concurrent.atomic.AtomicReference<>();
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
                    original.set(new java.util.HashMap<>(prefs.getAll()));
                    P7DesignStudio studio = studioForModalRegression(activity);
                    int current = P7ThemeCatalog.currentTheme(activity);
                    String choice = P7ThemeCatalog.nameAt(current == 0 ? 1 : 0);
                    assertTrue(byDescription(root, choice + ",").performClick());
                    android.app.AlertDialog dialog = studio.activeThemeConfirmation();
                    pending.set(dialog);
                    assertNotNull("Theme confirmation must open", dialog);
                    assertTrue(dialog.isShowing());
                    int layout = P7VisualCatalog.currentLayout(activity);
                    String otherLayout = P7VisualCatalog.LAYOUT_NAMES[
                        layout == 0 ? 1 : 0];
                    assertTrue(byDescription(root, otherLayout + ",").performClick());
                    assertNull("Layout cannot stack behind theme confirmation",
                        studio.activeLayoutConfirmation());
                    int preset = P7VisualCatalog.currentPreset(activity);
                    String otherPreset = P7VisualCatalog.PRESET_NAMES[
                        preset == 0 ? 1 : 0];
                    assertTrue(byDescription(root, otherPreset + ",").performClick());
                    assertNull("Preset cannot stack behind theme confirmation",
                        studio.activePresetConfirmation());
                    assertTrue("Original theme confirmation must survive blocked taps",
                        dialog.isShowing());
                    assertNotNull(byDescription(root,
                        P7VisualCatalog.LAYOUT_NAMES[layout] + ", layout aplicado"));
                    assertEquals("Blocked choices cannot save preferences",
                        original.get(), prefs.getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                });
                // OnDismiss is posted by AlertDialog after its button callback.
                // Starting a different confirmation in the SAME main-thread
                // onActivity block is not a valid user-visible interaction.
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    P7DesignStudio studio = studioForModalRegression(activity);
                    assertNotNull(pending.get());
                    assertFalse("Theme must finish dismissal before next modal",
                        pending.get().isShowing());
                    assertNull("Theme OnDismiss must release the reference",
                        studio.activeThemeConfirmation());
                    View root = activity.getWindow().getDecorView();
                    int applied = P7VisualCatalog.currentLayout(activity);
                    String choice = P7VisualCatalog.LAYOUT_NAMES[
                        applied == 0 ? 1 : 0];
                    assertTrue(byDescription(root, choice + ",").performClick());
                    android.app.AlertDialog dialog = studio.activeLayoutConfirmation();
                    pending.set(dialog);
                    assertNotNull("Layout confirmation must open after theme closes",
                        dialog);
                    assertTrue(dialog.isShowing());
                    int current = P7ThemeCatalog.currentTheme(activity);
                    String themeChoice = P7ThemeCatalog.nameAt(
                        current == 0 ? 1 : 0);
                    assertTrue(byDescription(root, themeChoice + ",").performClick());
                    assertNull("Theme cannot stack behind layout confirmation",
                        studio.activeThemeConfirmation());
                    int preset = P7VisualCatalog.currentPreset(activity);
                    String presetChoice = P7VisualCatalog.PRESET_NAMES[
                        preset == 0 ? 1 : 0];
                    assertTrue(byDescription(root, presetChoice + ",").performClick());
                    assertNull("Preset cannot stack behind layout confirmation",
                        studio.activePresetConfirmation());
                    assertTrue(dialog.isShowing());
                    assertEquals(original.get(), activity.getSharedPreferences(
                        "v3_personalizacao", 0).getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    P7DesignStudio studio = studioForModalRegression(activity);
                    assertNotNull(pending.get());
                    assertFalse(pending.get().isShowing());
                    assertNull("Layout OnDismiss must release its reference",
                        studio.activeLayoutConfirmation());
                    View root = activity.getWindow().getDecorView();
                    int current = P7VisualCatalog.currentPreset(activity);
                    String choice = P7VisualCatalog.PRESET_NAMES[
                        current == 0 ? 1 : 0];
                    assertTrue(byDescription(root, choice + ",").performClick());
                    android.app.AlertDialog dialog = studio.activePresetConfirmation();
                    pending.set(dialog);
                    assertNotNull("Preset confirmation must open after layout closes",
                        dialog);
                    assertTrue(dialog.isShowing());
                    int theme = P7ThemeCatalog.currentTheme(activity);
                    String otherTheme = P7ThemeCatalog.nameAt(theme == 0 ? 1 : 0);
                    assertTrue(byDescription(root, otherTheme + ",").performClick());
                    assertNull("Theme cannot stack behind preset confirmation",
                        studio.activeThemeConfirmation());
                    int layout = P7VisualCatalog.currentLayout(activity);
                    String otherLayout = P7VisualCatalog.LAYOUT_NAMES[
                        layout == 0 ? 1 : 0];
                    assertTrue(byDescription(root, otherLayout + ",").performClick());
                    assertNull("Layout cannot stack behind preset confirmation",
                        studio.activeLayoutConfirmation());
                    assertTrue(dialog.isShowing());
                    assertEquals("No cross-family tap may save or alter appearance",
                        original.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    P7DesignStudio studio = studioForModalRegression(activity);
                    assertNotNull(pending.get());
                    assertFalse(pending.get().isShowing());
                    assertNull(studio.activeThemeConfirmation());
                    assertNull(studio.activeLayoutConfirmation());
                    assertNull(studio.activePresetConfirmation());
                    assertNull(studio.activeCatalogChooser());
                    assertEquals("All blocked previews must remain uncommitted",
                        original.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    String savedLayout = P7VisualCatalog.LAYOUT_NAMES[
                        P7VisualCatalog.currentLayout(activity)];
                    assertNotNull(byDescription(
                        activity.getWindow().getDecorView(),
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

    /**
     * Android Back, unlike the native Fechar button, triggers cancel/dismiss
     * callbacks. It must release the chooser, preserve every preference and
     * permit reopening any catalog on the same Activity.
     */
    @Test public void androidBackClosesEveryCatalogWithoutCommittingAppearance() {
        final String[] sections = {
            "Previews de Temas", "Opções de Layout", "Presets de Aparência"
        };
        final java.util.concurrent.atomic.AtomicReference<java.util.Map<String, ?>>
            original = new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            opened = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertAccessibleButton(design);
                    assertTrue(design.performClick());
                    original.set(new java.util.HashMap<>(activity
                        .getSharedPreferences("v3_personalizacao", 0).getAll()));
                });
                for (String section : sections) {
                    scenario.onActivity(activity -> {
                        View root = activity.getWindow().getDecorView();
                        View opener = byDescription(root, "Ver todos: " + section);
                        assertAccessibleButton(opener);
                        assertTrue("Native chooser must open before Android Back",
                            opener.performClick());
                        P7DesignStudio studio = studioForModalRegression(activity);
                        android.app.AlertDialog chooser = studio.activeCatalogChooser();
                        opened.set(chooser);
                        assertNotNull(chooser);
                        assertTrue(chooser.isShowing());
                        assertNotNull(chooser.getWindow());
                        assertEquals("Opening catalog must not change preferences",
                            original.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                    });
                    // dialog.show() posts window attach/traversal to the main
                    // looper. Check real attachment AFTER that work completes,
                    // not in the same synchronous ActivityScenario callback.
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        P7DesignStudio studio = studioForModalRegression(activity);
                        android.app.AlertDialog chooser = opened.get();
                        assertNotNull(chooser);
                        assertSame("The same native chooser must remain active",
                            chooser, studio.activeCatalogChooser());
                        assertTrue(chooser.isShowing());
                        assertTrue("Real chooser must attach before Android Back",
                            chooser.getWindow().getDecorView()
                                .isAttachedToWindow());
                    });
                    InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(
                        android.view.KeyEvent.KEYCODE_BACK);
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        P7DesignStudio studio = studioForModalRegression(activity);
                        assertNotNull(opened.get());
                        assertFalse("Android Back must dismiss native chooser",
                            opened.get().isShowing());
                        assertNull("Android Back must clear native chooser handle",
                            studio.activeCatalogChooser());
                        assertNull(studio.activeThemeConfirmation());
                        assertNull(studio.activeLayoutConfirmation());
                        assertNull(studio.activePresetConfirmation());
                        assertEquals("Android Back cannot commit catalog values",
                            original.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                        View opener = byDescription(
                            activity.getWindow().getDecorView(),
                            "Ver todos: " + section);
                        assertAccessibleButton(opener);
                        assertTrue("Catalog must reopen after Back", opener.performClick());
                        android.app.AlertDialog reopened = studio.activeCatalogChooser();
                        opened.set(reopened);
                        assertNotNull(reopened);
                        assertTrue(reopened.isShowing());
                        assertTrue("Reopened chooser must accept Fechar",
                            reopened.getButton(
                                android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    });
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        P7DesignStudio studio = studioForModalRegression(activity);
                        assertNotNull(opened.get());
                        assertFalse("Reopened chooser must finish dismissing",
                            opened.get().isShowing());
                        assertNull(studio.activeCatalogChooser());
                        assertEquals("Reopening and closing must never save appearance",
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

    /**
     * Hardware/system Back cancellation must roll back the SAME native preview
     * as Cancelar, across all three appearance families. Never commit on Back.
     */
    @Test public void androidBackRollsBackThemeLayoutAndPresetConfirmations() {
        final java.util.concurrent.atomic.AtomicReference<java.util.Map<String, ?>>
            saved = new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<android.app.AlertDialog>
            pending = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View design = byDescription(root, "Abrir seção Design");
                    assertAccessibleButton(design);
                    assertTrue(design.performClick());
                    saved.set(new java.util.HashMap<>(activity
                        .getSharedPreferences("v3_personalizacao", 0).getAll()));
                });
                for (int type = 0; type < 3; type++) {
                    final int kind = type;
                    scenario.onActivity(activity -> {
                        P7DesignStudio studio = studioForModalRegression(activity);
                        int applied = kind == 0
                            ? P7ThemeCatalog.currentTheme(activity)
                            : kind == 1 ? P7VisualCatalog.currentLayout(activity)
                            : P7VisualCatalog.currentPreset(activity);
                        int alternative = applied == 0 ? 1 : 0;
                        String[] options = kind == 0
                            ? P7ThemeCatalog.names()
                            : kind == 1 ? P7VisualCatalog.LAYOUT_NAMES
                            : P7VisualCatalog.PRESET_NAMES;
                        assertTrue(alternative < options.length);
                        View proposed = byDescription(
                            activity.getWindow().getDecorView(),
                            options[alternative] + ", selecionar prévia");
                        assertAccessibleButton(proposed);
                        assertTrue("Preview tap opens a real Apply confirmation",
                            proposed.performClick());
                        android.app.AlertDialog dialog = kind == 0
                            ? studio.activeThemeConfirmation()
                            : kind == 1 ? studio.activeLayoutConfirmation()
                            : studio.activePresetConfirmation();
                        pending.set(dialog);
                        assertNotNull(dialog);
                        assertTrue("Native confirmation must be visible before Back",
                            dialog.isShowing());
                        assertNull(studio.activeCatalogChooser());
                        assertEquals(saved.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    });
                    // A newly shown AlertDialog can report isShowing()
                    // before WindowManager attaches and focuses its window.
                    // Sending BACK then may target the Activity behind it.
                    // Probe the SAME native dialog with a bounded wait;
                    // never cancel or retry Back to manufacture success.
                    java.util.concurrent.atomic.AtomicBoolean backWindowReady =
                        new java.util.concurrent.atomic.AtomicBoolean(false);
                    for (int attempt = 0; attempt < 12
                            && !backWindowReady.get(); attempt++) {
                        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                        scenario.onActivity(activity -> {
                            android.app.AlertDialog dialog = pending.get();
                            assertNotNull("Apply confirmation lost before Back", dialog);
                            P7DesignStudio studio = studioForModalRegression(activity);
                            assertSame("Focus probe must target the original Apply dialog",
                                dialog, kind == 0 ? studio.activeThemeConfirmation()
                                    : kind == 1 ? studio.activeLayoutConfirmation()
                                    : studio.activePresetConfirmation());
                            android.view.Window window = dialog.getWindow();
                            backWindowReady.set(dialog.isShowing()
                                && window != null
                                && window.getDecorView().isAttachedToWindow()
                                && window.getDecorView().hasWindowFocus());
                        });
                        if (!backWindowReady.get())
                            android.os.SystemClock.sleep(150);
                    }
                    assertTrue("Apply confirmation must own a focused and attached "
                        + "native window BEFORE Android Back", backWindowReady.get());
                    InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(
                        android.view.KeyEvent.KEYCODE_BACK);
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        assertNotNull(pending.get());
                        assertFalse("Android Back must dismiss Apply confirmation",
                            pending.get().isShowing());
                        P7DesignStudio studio = studioForModalRegression(activity);
                        assertNull("Back clears theme Apply handle",
                            studio.activeThemeConfirmation());
                        assertNull("Back clears layout Apply handle",
                            studio.activeLayoutConfirmation());
                        assertNull("Back clears preset Apply handle",
                            studio.activePresetConfirmation());
                        assertNull(studio.activeCatalogChooser());
                        assertEquals("Android Back cannot save appearance changes",
                            saved.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                        int applied = kind == 0
                            ? P7ThemeCatalog.currentTheme(activity)
                            : kind == 1 ? P7VisualCatalog.currentLayout(activity)
                            : P7VisualCatalog.currentPreset(activity);
                        int alternative = applied == 0 ? 1 : 0;
                        String[] options = kind == 0
                            ? P7ThemeCatalog.names()
                            : kind == 1 ? P7VisualCatalog.LAYOUT_NAMES
                            : P7VisualCatalog.PRESET_NAMES;
                        View restored = byDescription(
                            activity.getWindow().getDecorView(),
                            options[alternative] + ", selecionar prévia");
                        assertAccessibleButton(restored);
                        assertTrue("Back must restore unselected preview",
                            restored.getContentDescription().toString().startsWith(
                                options[alternative] + ", selecionar prévia"));
                        assertTrue("After Back the same confirmation must reopen",
                            restored.performClick());
                        android.app.AlertDialog reopened = kind == 0
                            ? studio.activeThemeConfirmation()
                            : kind == 1 ? studio.activeLayoutConfirmation()
                            : studio.activePresetConfirmation();
                        pending.set(reopened);
                        assertNotNull(reopened);
                        assertTrue(reopened.isShowing());
                        assertTrue("Reopened Apply must accept Cancelar",
                            reopened.getButton(
                                android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                    });
                    InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                    scenario.onActivity(activity -> {
                        P7DesignStudio studio = studioForModalRegression(activity);
                        assertNotNull(pending.get());
                        assertFalse("Cancelar must dismiss reopened confirmation",
                            pending.get().isShowing());
                        assertNull(studio.activeThemeConfirmation());
                        assertNull(studio.activeLayoutConfirmation());
                        assertNull(studio.activePresetConfirmation());
                        assertNull(studio.activeCatalogChooser());
                        assertEquals("Back and Cancelar must preserve all preferences",
                            saved.get(), activity.getSharedPreferences(
                                "v3_personalizacao", 0).getAll());
                    });
                    pending.set(null);
                }
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.app.AlertDialog dialog = pending.get();
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

    /** Reference Home section typography must stay readable on every palette. */
    @Test public void homeQuickActionsHeadingUsesReferenceTextColorAcrossThemes() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadTheme = prefs.contains("theme");
        String previousTheme = prefs.getString("theme", "oled");
        try {
            for (String theme : new String[]{"oled", "graphite", "light"}) {
                assertTrue(prefs.edit().putString("theme", theme).commit());
                try (ActivityScenario<MainActivity> scenario =
                        ActivityScenario.launch(MainActivity.class)) {
                    scenario.onActivity(activity -> {
                        View root = activity.getWindow().getDecorView();
                        TextView heading = accessibleHeading(root, "Ações rápidas");
                        assertNotNull("Real Home quick-actions heading must exist",
                            heading);
                        assertEquals("Reference Home uses foreground text, "
                                + "not the blue accent, for section headings",
                            NegrescoTheme.TEXT, heading.getCurrentTextColor());
                        assertTrue("Section title must remain visually readable",
                            NegrescoTheme.contrastRatio(
                                heading.getCurrentTextColor(),
                                NegrescoTheme.BACKGROUND) >= 4.5);
                        assertTrue("Heading must keep 15sp hierarchy",
                            heading.getTextSize() >= 14f
                                * activity.getResources()
                                    .getDisplayMetrics().scaledDensity
                                * NegrescoTheme.FONT_SCALE);
                        assertFalse("Headings are not action buttons",
                            heading.isClickable());
                    });
                }
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadTheme) restore.putString("theme", previousTheme);
            else restore.remove("theme");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }

    @Test public void designOverflowIsRealAccessibleMenuAndCatalogOpensWithoutApplying()
            throws Exception {
        final java.util.concurrent.atomic.AtomicReference<
            java.util.Map<String, ?>> before = new java.util.concurrent.atomic.AtomicReference<>();
        final java.util.concurrent.atomic.AtomicReference<
            android.widget.PopupMenu> popup = new java.util.concurrent.atomic.AtomicReference<>();
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            try {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    assertTrue(byDescription(root, "Abrir seção Design").performClick());
                    View overflow = byDescription(root, "Mais opções do Design Studio");
                    assertNotNull("The approved three-dot action must exist", overflow);
                    assertAccessibleButton(overflow);
                    int min = NegrescoTheme.dp(activity, 48);
                    assertTrue("Overflow hit target cannot shrink below 48dp",
                        overflow.getMinimumWidth() >= min
                            && overflow.getMinimumHeight() >= min);
                    assertTrue(overflow.getLayoutParams().width >= min
                        && overflow.getLayoutParams().height >= min);
                    android.content.SharedPreferences prefs =
                        activity.getSharedPreferences("v3_personalizacao", 0);
                    before.set(new java.util.HashMap<>(prefs.getAll()));
                    assertTrue("Three-dot menu must open", overflow.performClick());
                    P7DesignStudio studio = studioForModalRegression(activity);
                    android.widget.PopupMenu menu = studio.activeOverflowMenu();
                    assertNotNull("Actual Android PopupMenu must be visible", menu);
                    popup.set(menu);
                    assertEquals("Only implemented, reusable actions may be listed",
                        3, menu.getMenu().size());
                    assertEquals("Catálogo de temas",
                        menu.getMenu().findItem(1).getTitle().toString());
                    assertEquals("Criador de ícones",
                        menu.getMenu().findItem(2).getTitle().toString());
                    assertEquals("Logo Studio",
                        menu.getMenu().findItem(3).getTitle().toString());
                    assertTrue("Click must trigger the actual native catalog",
                        menu.getMenu().performIdentifierAction(1, 0));
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    P7DesignStudio studio = studioForModalRegression(activity);
                    android.app.AlertDialog chooser = studio.activeCatalogChooser();
                    assertNotNull("Overflow choice must open real catalog", chooser);
                    assertTrue(chooser.isShowing());
                    assertEquals("Browsing overflow cannot save appearance",
                        before.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    chooser.cancel();
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNull("Dismissed catalog cannot leave an active handle",
                        studioForModalRegression(activity).activeCatalogChooser());
                    assertEquals("Back/cancel must preserve saved appearance",
                        before.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                });
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                    android.widget.PopupMenu active = popup.get();
                    if (active != null) active.dismiss();
                });
            }
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

        // At the reference viewport, four native theme previews can share
        // the first rail. Never sacrifice accessibility sizes or tablet
        // proportions just to fit a promotional screenshot.
        assertEquals(80, P7DesignStudio.themeCardWidthDp(393, 1f));
        assertEquals(80, P7DesignStudio.themeCardWidthDp(390, 1.15f));
        assertEquals(100, P7DesignStudio.themeCardWidthDp(389, 1f));
        assertEquals(100, P7DesignStudio.themeCardWidthDp(600, 1f));
        assertEquals(144, P7DesignStudio.themeCardWidthDp(393, 1.3f));
        assertEquals(144, P7DesignStudio.themeCardWidthDp(320, 2f));


        // Real font metrics, not arbitrary character counts, decide whether
        // the reference's same-line compact heading can fit safely.
        assertTrue(P7DesignStudio.compactHeadingFitsInOneRow(
            320, 1.3f, 1f, 135f, 80f, 1f));
        assertFalse(P7DesignStudio.compactHeadingFitsInOneRow(
            320, 1.3f, 1f, 225f, 95f, 1f));
        assertFalse(P7DesignStudio.compactHeadingFitsInOneRow(
            320, 2f, 1f, 135f, 80f, 1f));
        assertFalse(P7DesignStudio.compactHeadingFitsInOneRow(
            393, 1.3f, 1f, 135f, 80f, 1f));
        assertFalse(P7DesignStudio.compactHeadingFitsInOneRow(
            320, 1.3f, 1.35f, 135f, 80f, 1f));

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

    @Test public void appliedDesignBadgeRespectsSavedAccentAndReadableCheck() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadTheme = prefs.contains("theme");
        String oldTheme = prefs.getString("theme", "oled");
        boolean hadAccent = prefs.contains("accent");
        String oldAccent = prefs.getString("accent", "blue");
        boolean hadCustom = prefs.contains("custom_accent");
        String oldCustom = prefs.getString("custom_accent", "#1688FF");
        try {
            for (String[] sample : new String[][]{
                    {"oled", "blue", "#1688FF"},
                    {"light", "green", "#1688FF"},
                    {"graphite", "orange", "#1688FF"},
                    {"oled", "purple", "#1688FF"},
                    {"light", "custom", "#FFFFFF"},
                    {"oled", "custom", "#050505"}}) {
                assertTrue(prefs.edit().putString("theme", sample[0])
                    .putString("accent", sample[1])
                    .putString("custom_accent", sample[2]).commit());
                NegrescoTheme.apply(context);
                try (ActivityScenario<MainActivity> scenario =
                        ActivityScenario.launch(MainActivity.class)) {
                    scenario.onActivity(activity -> {
                        View root = activity.getWindow().getDecorView();
                        View design = byDescription(root, "Abrir seção Design");
                        assertAccessibleButton(design);
                        assertTrue(design.performClick());
                        int applied = P7VisualCatalog.currentLayout(activity);
                        String name = P7VisualCatalog.LAYOUT_NAMES[applied];
                        View tile = byDescription(
                            activity.getWindow().getDecorView(),
                            name + ", layout aplicado");
                        assertAccessibleButton(tile);
                        View preview = ((ViewGroup) tile).getChildAt(0);
                        assertTrue(preview instanceof ViewGroup);
                        assertEquals("Committed choice must retain exactly one badge",
                            2, ((ViewGroup) preview).getChildCount());
                        View checkView = ((ViewGroup) preview).getChildAt(1);
                        assertTrue(checkView instanceof TextView);
                        TextView check = (TextView) checkView;
                        assertEquals("✓", check.getText().toString());
                        assertTrue(check.getBackground() instanceof
                            android.graphics.drawable.GradientDrawable);
                        android.graphics.drawable.GradientDrawable fill =
                            (android.graphics.drawable.GradientDrawable)
                                check.getBackground();
                        assertNotNull(fill.getColor());
                        assertEquals("Applied badge must use the SAVED accent",
                            NegrescoTheme.ACCENT, fill.getColor().getDefaultColor());
                        assertEquals("Check must retain white on approved blue "
                                + "or select contrasting ink for custom accents",
                            P7DesignStudio.appliedBadgeGlyphColor(
                                NegrescoTheme.ACCENT), check.getCurrentTextColor());
                        assertTrue("Graphical applied indicator must retain "
                                + "at least 3:1 non-text contrast",
                            NegrescoTheme.contrastRatio(
                                fill.getColor().getDefaultColor(),
                                check.getCurrentTextColor()) >= 3.0);
                        if ("blue".equals(sample[1]))
                            assertEquals("Approved blue badge retains white glyph",
                                android.graphics.Color.WHITE,
                                check.getCurrentTextColor());
                        assertEquals("Viewing Design must never change preferences",
                            sample[1], prefs.getString("accent", ""));
                    });
                }
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadTheme) restore.putString("theme", oldTheme);
            else restore.remove("theme");
            if (hadAccent) restore.putString("accent", oldAccent);
            else restore.remove("accent");
            if (hadCustom) restore.putString("custom_accent", oldCustom);
            else restore.remove("custom_accent");
            assertTrue(restore.commit());
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
        final java.util.concurrent.atomic.AtomicReference<java.util.Map<String, ?>>
            original = new java.util.concurrent.atomic.AtomicReference<>();
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
                    original.set(new java.util.HashMap<>(prefs.getAll()));
                    P7DesignStudio studio = studioForModalRegression(activity);
                    int current = P7ThemeCatalog.currentTheme(activity);
                    String appliedName = P7ThemeCatalog.nameAt(current);
                    String proposalName = P7ThemeCatalog.nameAt(
                        current == 0 ? 1 : 0);
                    View committed = byDescription(
                        root, appliedName + ", tema aplicado");
                    assertAccessibleButton(committed);
                    assertEquals("Saved theme keeps blue check", 2,
                        ((ViewGroup) ((ViewGroup) committed)
                            .getChildAt(0)).getChildCount());
                    View selectable = byDescription(
                        root, proposalName + ", selecionar prévia");
                    assertAccessibleButton(selectable);
                    assertTrue(selectable.performClick());
                    android.app.AlertDialog dialog = studio.activeThemeConfirmation();
                    pending.set(dialog);
                    assertNotNull(dialog);
                    assertTrue(dialog.isShowing());
                    View preview = byDescription(root,
                        proposalName + ", prévia escolhida, ainda não aplicada");
                    assertAccessibleButton(preview);
                    assertEquals("Pending theme has no applied badge", 1,
                        ((ViewGroup) ((ViewGroup) preview)
                            .getChildAt(0)).getChildCount());
                    assertNotNull(byDescription(
                        root, appliedName + ", tema aplicado"));
                    assertEquals("Unconfirmed theme must not change preferences",
                        original.get(), prefs.getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull(pending.get());
                    assertFalse("Theme must close before layout can open",
                        pending.get().isShowing());
                    P7DesignStudio studio = studioForModalRegression(activity);
                    assertNull(studio.activeThemeConfirmation());
                    View root = activity.getWindow().getDecorView();
                    int current = P7VisualCatalog.currentLayout(activity);
                    String savedName = P7VisualCatalog.LAYOUT_NAMES[current];
                    String proposal = P7VisualCatalog.LAYOUT_NAMES[
                        current == 0 ? 1 : 0];
                    View committed = byDescription(
                        root, savedName + ", layout aplicado");
                    assertAccessibleButton(committed);
                    assertEquals("Saved layout keeps blue check", 2,
                        ((ViewGroup) ((ViewGroup) committed)
                            .getChildAt(0)).getChildCount());
                    View selectable = byDescription(root,
                        proposal + ", selecionar prévia");
                    assertAccessibleButton(selectable);
                    assertTrue(selectable.performClick());
                    android.app.AlertDialog dialog = studio.activeLayoutConfirmation();
                    pending.set(dialog);
                    assertNotNull("Layout must open after theme dismisses", dialog);
                    assertTrue(dialog.isShowing());
                    View preview = byDescription(root,
                        proposal + ", prévia escolhida, ainda não aplicada");
                    assertAccessibleButton(preview);
                    assertEquals("Pending layout has no applied badge", 1,
                        ((ViewGroup) ((ViewGroup) preview)
                            .getChildAt(0)).getChildCount());
                    assertNotNull(byDescription(
                        root, savedName + ", layout aplicado"));
                    assertEquals("Unconfirmed layout cannot save appearance",
                        original.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    assertTrue(dialog.getButton(
                        android.app.AlertDialog.BUTTON_NEGATIVE).performClick());
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull(pending.get());
                    assertFalse(pending.get().isShowing());
                    P7DesignStudio studio = studioForModalRegression(activity);
                    assertNull("Layout dialog must release its reference",
                        studio.activeLayoutConfirmation());
                    assertNull(studio.activeThemeConfirmation());
                    assertEquals("Both cancels preserve all appearance preferences",
                        original.get(), activity.getSharedPreferences(
                            "v3_personalizacao", 0).getAll());
                    String saved = P7VisualCatalog.LAYOUT_NAMES[
                        P7VisualCatalog.currentLayout(activity)];
                    assertNotNull(byDescription(
                        activity.getWindow().getDecorView(),
                        saved + ", layout aplicado"));
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
