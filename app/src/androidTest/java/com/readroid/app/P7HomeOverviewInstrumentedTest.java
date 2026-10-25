package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.net.Uri;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicInteger;
import android.widget.TextView;
import android.widget.LinearLayout;
import android.widget.ImageView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class P7HomeOverviewInstrumentedTest {
    private static boolean contains(View v, String text) {
        if (v instanceof TextView &&
                text.equals(((TextView) v).getText().toString())) return true;
        if (v instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) v;
            for (int i = 0; i < parent.getChildCount(); i++)
                if (contains(parent.getChildAt(i), text)) return true;
        }
        return false;
    }

    private static View byDescription(View v, String description) {
        if (description.equals(v.getContentDescription())) return v;
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) {
                View found = byDescription(g.getChildAt(i), description);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static void assertAccessibleButton(View view, String description) {
        AccessibilityNodeInfo node = view.createAccessibilityNodeInfo();
        assertNotNull("Accessibility node is required", node);
        try {
            assertEquals("Action must be exposed as a Button to TalkBack",
                android.widget.Button.class.getName(),
                node.getClassName().toString());
            assertEquals(description, node.getContentDescription().toString());
            assertTrue("Action needs a clickable accessibility node",
                node.isClickable());
            assertTrue("Action needs to be keyboard-focusable", view.isFocusable());
        } finally {
            node.recycle();
        }
    }

    @Test public void narrowBrandTaglineKeepsEveryWordAndCustomSubtitles() {
        final String full = "ANÁLISE, EDIÇÃO E CUSTOMIZAÇÃO DE APKS";
        final String narrow = "ANÁLISE, EDIÇÃO E\nCUSTOMIZAÇÃO DE APKS";
        assertEquals(narrow, MainActivity.brandSubtitleForViewport(
            "APK ENGINEERING STUDIO", 320, 1.3f, 1f));
        assertEquals(narrow, MainActivity.brandSubtitleForViewport(
            "APK ENGINEERING STUDIO", 359, 1f, 1.35f));
        assertEquals(full, MainActivity.brandSubtitleForViewport(
            "APK ENGINEERING STUDIO", 320, 1f, 1f));
        assertEquals(full, MainActivity.brandSubtitleForViewport(
            "APK ENGINEERING STUDIO", 393, 1.3f, 1f));
        assertEquals(full, MainActivity.brandSubtitleForViewport(
            "APK ENGINEERING STUDIO", 360, 1.3f, 1f));
        assertEquals(full, narrow.replace("\n", " "));
        for (String custom : new String[]{
                "CUSTOM PERSONALIZADO", "MEU PROJETO APK", "",
                "ANÁLISE, EDIÇÃO E CUSTOMIZAÇÃO DE APKS"}) {
            assertEquals("User-saved subtitle must never be rewritten",
                custom, MainActivity.brandSubtitleForViewport(
                    custom, 320, 2f, 1.35f));
        }
        assertNull(MainActivity.brandSubtitleForViewport(
            null, 320, 1.3f, 1f));
    }

    @Test public void recentProjectMenuIsAccessibleWithoutDeletingOriginal() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                P7HomeOverview panel = new P7HomeOverview(activity, v -> {});
                activity.setContentView(panel);
                // A synthetic history item does not persist a SAF grant or
                // create/modify any APK. Cached artwork safely falls back.
                P7ProjectHistory.Entry item = new P7ProjectHistory.Entry(
                    Uri.parse("content://p7.synthetic/project.apk"),
                    "Fixture.apk", "com.example.synthetic", 0);
                AtomicInteger allOpens = new AtomicInteger();
                panel.setHistoryCallbacks(entry -> {},
                    v -> allOpens.incrementAndGet());
                panel.setRecentProjects(Collections.singletonList(item), null);
                View history = byDescription(panel,
                    "Ver todos os projetos recentes");
                assertNotNull("History link must exist when a project is present",
                    history);
                int touch = NegrescoTheme.dp(activity, 48);
                assertEquals(View.VISIBLE, history.getVisibility());
                assertTrue(history.getMinimumHeight() >= touch);
                assertTrue(history.isClickable() && history.isFocusable());
                assertAccessibleButton(history, "Ver todos os projetos recentes");
                assertTrue(history.performClick());
                assertEquals(1, allOpens.get());
                View menu = byDescription(panel, "Mais opções de Fixture.apk");
                assertNotNull("Historical overflow missing", menu);
                assertTrue(menu.getLayoutParams().width >= touch);
                assertTrue(menu.getLayoutParams().height >= touch);
                assertTrue(menu.getMinimumWidth() >= touch);
                assertTrue(menu.getMinimumHeight() >= touch);
                assertTrue(menu.isClickable() && menu.isFocusable());
                assertAccessibleButton(menu, "Mais opções de Fixture.apk");
                assertNotNull("Menu listener must remain operational",
                    menu.hasOnClickListeners() ? menu : null);
            });
        }
    }

    @Test public void statisticsSpeakVerifiedValuesAndExplicitlyUnknownMetrics()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    P7HomeOverview panel = new P7HomeOverview(activity, v -> {});
                    activity.setContentView(panel);
                    LinearLayout top = (LinearLayout) panel.getChildAt(0);
                    LinearLayout bottom = (LinearLayout) panel.getChildAt(1);
                    LinearLayout projects = (LinearLayout) top.getChildAt(0);
                    LinearLayout files = (LinearLayout) top.getChildAt(1);
                    LinearLayout builds = (LinearLayout) bottom.getChildAt(0);
                    LinearLayout threats = (LinearLayout) bottom.getChildAt(1);
                    assertStatLabel(projects, "Projetos: 0");
                    assertStatLabel(files, "Arquivos: não disponível");
                    assertStatLabel(builds, "APKs Builds: não disponível");
                    assertStatLabel(threats, "Ameaças: não disponível");
                    // The visual text still exists, but is not spoken twice.
                    LinearLayout metrics = (LinearLayout) files.getChildAt(1);
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                        metrics.getChildAt(0).getImportantForAccessibility());
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                        metrics.getChildAt(1).getImportantForAccessibility());

                    JSONObject verified = new JSONObject();
                    verified.put("explorer", new JSONObject().put("fileCount", 301));
                    panel.update(verified, 0);
                    assertStatLabel(projects, "Projetos: 1");
                    assertStatLabel(files, "Arquivos: 301");
                    assertStatLabel(builds, "APKs Builds: não disponível");
                    assertStatLabel(threats, "Ameaças: não disponível");

                    panel.update(null, 0);
                    assertStatLabel(projects, "Projetos: 0");
                    assertStatLabel(files, "Arquivos: não disponível");
                } catch (Exception error) {
                    throw new AssertionError(error);
                }
            });
        }
    }

    private static void assertStatLabel(View cell, String expected) {
        assertEquals(expected, cell.getContentDescription().toString());
        assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_YES,
            cell.getImportantForAccessibility());
        assertTrue("Statistics must support keyboard accessibility focus",
            cell.isFocusable());
        AccessibilityNodeInfo node = cell.createAccessibilityNodeInfo();
        assertNotNull(node);
        try {
            assertEquals(expected, node.getContentDescription().toString());
            assertFalse("Read-only stats cannot pretend to be buttons",
                node.isClickable());
        } finally {
            node.recycle();
        }
    }

    @Test public void emptyAndActiveStatesNeverInventProjectHistoryOrSecurityResults()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    final P7HomeOverview panel = new P7HomeOverview(activity,
                        v -> { });
                    activity.setContentView(panel);
                    LinearLayout firstRow = (LinearLayout) panel.getChildAt(0);
                    LinearLayout projectStat = (LinearLayout) firstRow.getChildAt(0);
                    LinearLayout fileStat = (LinearLayout) firstRow.getChildAt(1);
                    assertEquals("Reference stat cards must align icon and data",
                        LinearLayout.HORIZONTAL, projectStat.getOrientation());
                    assertTrue("Project statistics require actual left icon",
                        projectStat.getChildAt(0) instanceof ImageView);
                    assertTrue("File statistics require actual left icon",
                        fileStat.getChildAt(0) instanceof ImageView);
                    assertTrue("Stacked statistics to the right of the icon",
                        projectStat.getChildAt(1) instanceof LinearLayout);
                    assertTrue(contains(panel, "Nenhum projeto aberto"));
                    assertTrue(contains(panel, "—"));
                    assertTrue(contains(panel,
                        "Abra um APK para começar seu histórico local."));
                    JSONObject current = new JSONObject();
                    current.put("explorer", new JSONObject().put("fileCount", 301));
                    current.put("manifestAnalysis", new JSONObject()
                        .put("packageName", "com.example.fixture"));
                    panel.update(current, 3);
                    assertTrue(contains(panel, "com.example.fixture"));
                    assertTrue(contains(panel, "301"));
                    assertTrue(contains(panel, "APKs Builds"));
                    assertTrue(contains(panel, "Ameaças"));
                    assertTrue("Unavailable counters must stay unknown",
                        contains(panel, "—"));
                    assertFalse(contains(panel, "Nenhum projeto aberto"));
                    panel.update(null, 0);
                    assertTrue(contains(panel, "Nenhum projeto aberto"));
                    assertTrue(contains(panel, "—"));
                } catch (Exception error) {
                    throw new AssertionError(error);
                }
            });
        }
    }
}
