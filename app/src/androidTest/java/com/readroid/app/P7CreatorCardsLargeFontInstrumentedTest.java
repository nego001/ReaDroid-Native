package com.readroid.app;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static com.readroid.app.P7NavigationInstrumentedTest.byDescription;

/**
 * Full real-Activity 135% accessibility/layout regression, in one mandatory
 * instrumented session so a device failure cannot abort unrelated navigation.
 */
@RunWith(AndroidJUnit4.class)
public final class P7CreatorCardsLargeFontInstrumentedTest {

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
}
