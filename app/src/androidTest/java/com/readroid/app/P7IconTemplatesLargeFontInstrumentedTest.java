package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Full large-font Icon Creator assertions, isolated for emulator stability. */
@RunWith(AndroidJUnit4.class)
public final class P7IconTemplatesLargeFontInstrumentedTest {
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

}
