package com.readroid.app;

import android.view.View;
import android.widget.TextView;
import android.widget.LinearLayout;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static com.readroid.app.P7NavigationInstrumentedTest.byDescription;
import static com.readroid.app.P7NavigationInstrumentedTest.describedView;
import static com.readroid.app.P7NavigationInstrumentedTest.clickableText;

/**
 * Runs the full existing accessible saved-identity preview regression at 135%
 * in its own Android instrumentation session, with unchanged assertions.
 */
@RunWith(AndroidJUnit4.class)
public final class P7LogoIdentityLargeFontInstrumentedTest {

    @Test public void logoPreviewAnnouncesSavedNameAndSubtitleWithoutDuplicateNodes() {
        android.content.Context context = InstrumentationRegistry
            .getInstrumentation().getTargetContext();
        android.content.SharedPreferences prefs = context.getSharedPreferences(
            "v3_personalizacao", android.content.Context.MODE_PRIVATE);
        boolean hadName = prefs.contains("display_name");
        String previousName = prefs.getString("display_name", "NegrecoDroid");
        boolean hadSubtitle = prefs.contains("display_subtitle");
        String previousSubtitle = prefs.getString(
            "display_subtitle", "APK ENGINEERING STUDIO");
        boolean hadFont = prefs.contains("font_percent");
        int previousFont = prefs.getInt("font_percent", 100);
        String testName = "NegrecoDroid Laboratório Mobile";
        String testSubtitle = "Análise e personalização de aplicativos Android";
        try {
            assertTrue(prefs.edit().putString("display_name", testName)
                .putString("display_subtitle", testSubtitle)
                .putInt("font_percent", 135).commit());
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    assertTrue(byDescription(root, "Abrir seção Design").performClick());
                    View tab = clickableText(root, "Logotipo");
                    assertNotNull(tab);
                    assertTrue(tab.performClick());
                    View preview = describedView(root,
                        "Prévia da identidade visual atual. Nome: ");
                    assertNotNull(preview);
                    assertEquals("Prévia da identidade visual atual. Nome: "
                        + testName + ". Subtítulo: " + testSubtitle,
                        preview.getContentDescription().toString());
                    assertFalse("Identity preview is information, not a button",
                        preview.isClickable());
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_YES,
                        preview.getImportantForAccessibility());
                    LinearLayout row = (LinearLayout) preview;
                    LinearLayout names = (LinearLayout) row.getChildAt(1);
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS,
                        names.getImportantForAccessibility());
                    TextView brand = (TextView) names.getChildAt(0);
                    TextView subtitle = (TextView) names.getChildAt(1);
                    assertEquals(testName, brand.getText().toString());
                    assertEquals(testSubtitle, subtitle.getText().toString());
                    assertEquals(Integer.MAX_VALUE, brand.getMaxLines());
                    assertEquals(Integer.MAX_VALUE, subtitle.getMaxLines());
                    assertEquals(-2, names.getLayoutParams().height);
                });
            }
        } finally {
            android.content.SharedPreferences.Editor restore = prefs.edit();
            if (hadName) restore.putString("display_name", previousName);
            else restore.remove("display_name");
            if (hadSubtitle) restore.putString("display_subtitle", previousSubtitle);
            else restore.remove("display_subtitle");
            if (hadFont) restore.putInt("font_percent", previousFont);
            else restore.remove("font_percent");
            assertTrue(restore.commit());
            NegrescoTheme.apply(context);
        }
    }
}
