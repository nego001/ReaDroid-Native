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
        if (description != null && label.equals(description.toString()))
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
    @Test public void bottomNavigationScalesWithoutClippingOrChangingLabels() {
        assertEquals(64, MainActivity.navTabHeightDp(393, 1f, 1f, true));
        assertEquals(64, MainActivity.navTabHeightDp(310, 1f, 1f, true));
        assertEquals(64, MainActivity.navTabHeightDp(310, 2f, 1.35f, false));
        assertTrue(MainActivity.navTabHeightDp(393, 1f, 1.35f, true) > 64);
        assertTrue(MainActivity.navTabHeightDp(310, 1.3f, 1.35f, true)
            > MainActivity.navTabHeightDp(310, 1f, 1.35f, true));
        assertTrue(MainActivity.navTabHeightDp(310, 3f, 1.35f, true) <= 120);

        android.content.Context context =
            InstrumentationRegistry.getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadFont = prefs.contains("font_percent");
        int beforeFont = prefs.getInt("font_percent", 100);
        boolean hadLabels = prefs.contains("nav_labels");
        boolean beforeLabels = prefs.getBoolean("nav_labels", true);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135)
                .putBoolean("nav_labels", true).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    String[] names = {"Início", "Arquivos", "Segurança", "Build", "Design"};
                    int expected = NegrescoTheme.dp(activity,
                        MainActivity.navTabHeightDp(
                            activity.getResources().getConfiguration().screenWidthDp,
                            activity.getResources().getConfiguration().fontScale,
                            NegrescoTheme.FONT_SCALE, true));
                    assertTrue("Large in-app font must enlarge nav touch targets",
                        expected > NegrescoTheme.dp(activity, 64));
                    for (String name : names) {
                        View tab = byDescription(root, "Abrir seção " + name);
                        assertNotNull("Missing accessible tab " + name, tab);
                        assertTrue("All five tabs must stay focusable", tab.isFocusable());
                        assertTrue(tab.isClickable());
                        assertEquals("Navigation row must reserve enlarged text",
                            expected, tab.getLayoutParams().height);
                        assertTrue(tab.getMinimumHeight() >= expected);
                        assertTrue(tab.getContentDescription().toString().contains(name));
                    }
                });
            }
        } finally {
            android.content.SharedPreferences.Editor revert = prefs.edit();
            if (hadFont) revert.putInt("font_percent", beforeFont);
            else revert.remove("font_percent");
            if (hadLabels) revert.putBoolean("nav_labels", beforeLabels);
            else revert.remove("nav_labels");
            assertTrue(revert.commit());
            NegrescoTheme.apply(context);
        }
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
                View dark = byDescription(root,"Negreco Blue, prévia selecionada");
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
                scenario.onActivity(activity -> {
                    LinearLayout fixture = new LinearLayout(activity);
                    fixture.setOrientation(LinearLayout.VERTICAL);
                    activity.setContentView(fixture, new ViewGroup.LayoutParams(
                        NegrescoTheme.dp(activity, 320), -1));
                    new P7DesignStudio(activity, fixture, new Button[13], 1);
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
                        assertEquals(2, title.getMaxLines());
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

    @Test public void welcomeCardGrowsWithLongTextInsteadOfClippingIt() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadFont = prefs.contains("font_percent");
        int priorFont = prefs.getInt("font_percent", 100);
        try {
            assertTrue(prefs.edit().putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                final int[] initialHeight = new int[1];
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View stage = root.findViewWithTag("p7-welcome-stage");
                    LinearLayout text = root.findViewWithTag("p7-welcome-text");
                    assertNotNull(stage);
                    assertNotNull(text);
                    assertEquals("Welcome stage must measure from its content",
                        -2, stage.getLayoutParams().height);
                    assertEquals(-2, text.getLayoutParams().height);
                    initialHeight[0] = stage.getHeight();
                    assertTrue(initialHeight[0] >= NegrescoTheme.dp(activity, 133));
                    TextView description = (TextView) text.getChildAt(2);
                    StringBuilder paragraph = new StringBuilder();
                    for (int i = 0; i < 35; i++)
                        paragraph.append("Descrição ampliada para acessibilidade. ");
                    description.setText(paragraph.toString());
                    stage.requestLayout();
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    View stage = root.findViewWithTag("p7-welcome-stage");
                    LinearLayout text = root.findViewWithTag("p7-welcome-text");
                    assertNotNull(stage);
                    assertNotNull(text);
                    assertTrue("A long message must grow the welcome card",
                        stage.getHeight() > initialHeight[0]);
                    assertTrue("Entire text stack must fit within welcome stage",
                        stage.getHeight() >= text.getHeight());
                    TextView description = (TextView) text.getChildAt(2);
                    assertNotNull(description.getLayout());
                    assertTrue("The test should require multiple wrapped lines",
                        description.getLayout().getLineCount() >= 10);
                    for (int line = 0; line < description.getLayout().getLineCount(); line++)
                        assertEquals("No hidden ellipsized lines", 0,
                            description.getLayout().getEllipsisCount(line));
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadFont) restore.putInt("font_percent", priorFont);
            else restore.remove("font_percent");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
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

    @Test public void fourIconTemplatesGrowWithLargeTextAndAnnounceSingleButtons() {
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
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    assertTrue(byDescription(root, "Abrir seção Design").performClick());
                    View iconsTab = clickableText(root, "Ícones");
                    assertNotNull(iconsTab);
                    assertTrue(iconsTab.performClick());
                });
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    for (String name : new String[]{
                            "Escudo Azul", "Código Neon", "Pasta Verde",
                            "Estrela Laranja"}) {
                        View found = byDescription(root, "Personalizar ícone " + name);
                        assertNotNull("Icon template must remain selectable " + name, found);
                        assertTrue(found instanceof LinearLayout);
                        LinearLayout tile = (LinearLayout) found;
                        assertEquals(-2, tile.getLayoutParams().height);
                        assertEquals(NegrescoTheme.dp(activity, 136),
                            tile.getLayoutParams().width);
                        assertTrue(tile.getMinimumHeight()
                            >= NegrescoTheme.dp(activity, 124));
                        assertTrue(tile.isClickable() && tile.isFocusable());
                        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                            tile.getChildAt(0).getImportantForAccessibility());
                        TextView caption = (TextView) tile.getChildAt(1);
                        assertEquals(name, caption.getText().toString());
                        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                            caption.getImportantForAccessibility());
                        assertNotNull(caption.getLayout());
                        assertTrue("Icon label must fit in tile height",
                            tile.getHeight() >= tile.getPaddingTop()
                                + tile.getChildAt(0).getHeight()
                                + caption.getHeight() + tile.getPaddingBottom());
                        View.AccessibilityDelegate delegate =
                            tile.getAccessibilityDelegate();
                        assertNotNull(delegate);
                        android.view.accessibility.AccessibilityNodeInfo node =
                            android.view.accessibility.AccessibilityNodeInfo.obtain();
                        try {
                            delegate.onInitializeAccessibilityNodeInfo(tile, node);
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
                assertNotNull("A prévia precisa ser acessível ao TalkBack",
                    describedView(window, "Prévia da identidade visual atual"));
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
