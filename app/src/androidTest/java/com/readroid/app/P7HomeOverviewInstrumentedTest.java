package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
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

    @Test public void emptyAndActiveStatesNeverInventProjectHistoryOrSecurityResults()
            throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    final P7HomeOverview panel = new P7HomeOverview(activity,
                        v -> { });
                    activity.setContentView(panel);
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
