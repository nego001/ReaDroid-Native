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
