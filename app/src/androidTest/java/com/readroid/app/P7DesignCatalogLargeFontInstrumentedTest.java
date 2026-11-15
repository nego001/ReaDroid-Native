package com.readroid.app;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static com.readroid.app.P7NavigationInstrumentedTest.byDescription;
import static com.readroid.app.P7NavigationInstrumentedTest.assertAccessibleButton;

/** Real Android 135% Design catalog regression, isolated from navigation. */
@RunWith(AndroidJUnit4.class)
public final class P7DesignCatalogLargeFontInstrumentedTest {

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
}
