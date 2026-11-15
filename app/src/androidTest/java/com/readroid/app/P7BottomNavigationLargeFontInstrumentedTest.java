package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Same full 135% font navigation regression, first isolated Android session. */
@RunWith(AndroidJUnit4.class)
public final class P7BottomNavigationLargeFontInstrumentedTest {
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

}
