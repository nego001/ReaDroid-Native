package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
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
