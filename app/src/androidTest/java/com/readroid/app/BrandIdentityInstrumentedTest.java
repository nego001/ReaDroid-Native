package com.readroid.app;

import android.content.Context;
import android.graphics.drawable.Drawable;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrandIdentityInstrumentedTest {
    @Test public void officialBrandAndLauncherIconResolve() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        // QA package intentionally appends "V3 Teste" to its launcher label.
        assertTrue(context.getString(R.string.app_name).startsWith("NegrecoDroid"));
        assertNotNull(context.getPackageManager().getApplicationIcon(context.getPackageName()));
    }

    @Test public void vectorAssetsResolveWithoutExternalImages() {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        Drawable logo = context.getDrawable(R.drawable.ic_negrecodroid_foreground);
        Drawable monochrome = context.getDrawable(R.drawable.ic_negrecodroid_monochrome);
        assertNotNull(logo);
        assertNotNull(monochrome);
        assertTrue(logo.getIntrinsicWidth() > 0);
        assertTrue(logo.getIntrinsicHeight() > 0);
    }
}
