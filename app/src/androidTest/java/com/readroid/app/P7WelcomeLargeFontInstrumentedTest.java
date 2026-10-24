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

/** Isolate the complete large-font welcome-card reflow assertions on API29/35. */
@RunWith(AndroidJUnit4.class)
public final class P7WelcomeLargeFontInstrumentedTest {
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

}
