package com.readroid.app;

import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.LayerDrawable;
import android.view.Gravity;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** A real file-browser row, not a multiline text mockup. */
@RunWith(AndroidJUnit4.class)
public final class P7ExplorerEntryRowInstrumentedTest {
    private static View descendant(View root, String description) {
        if (description.equals(root.getContentDescription())) return root;
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = descendant(group.getChildAt(i), description);
                if (found != null) return found;
            }
        }
        return null;
    }

    @Test public void distinctIconsAreChosenFromActualFileExtensions() {
        assertEquals(R.drawable.ic_p7_folder,
            P7ExplorerEntryRow.iconResource("assets/", true));
        assertEquals(R.drawable.ic_p7_image,
            P7ExplorerEntryRow.iconResource("res/banner.webp", false));
        assertEquals(R.drawable.ic_p7_image,
            P7ExplorerEntryRow.iconResource("logo.PNG", false));
        assertEquals(R.drawable.ic_p7_code,
            P7ExplorerEntryRow.iconResource("AndroidManifest.xml", false));
        assertEquals(R.drawable.ic_p7_code,
            P7ExplorerEntryRow.iconResource("smali/Main.smali", false));
        assertEquals(R.drawable.ic_p7_cube,
            P7ExplorerEntryRow.iconResource("classes.dex", false));
        assertEquals(R.drawable.ic_p7_cube,
            P7ExplorerEntryRow.iconResource("lib/arm64-v8a/libx.so", false));
        assertEquals(R.drawable.ic_p7_file,
            P7ExplorerEntryRow.iconResource("assets/data.txt", false));
        assertEquals(R.drawable.ic_p7_file,
            P7ExplorerEntryRow.iconResource("../unknown", false));
    }

    @Test public void folderAndFileProvideRealIconsLabelsAndSeparateActions() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                AtomicInteger opened = new AtomicInteger();
                AtomicInteger optionsOpened = new AtomicInteger();
                P7ExplorerEntryRow folder = new P7ExplorerEntryRow(activity,
                    "assets/", "Pasta", true, false,
                    v -> opened.incrementAndGet(),
                    v -> optionsOpened.incrementAndGet());

                assertEquals(LinearLayout.HORIZONTAL, folder.getOrientation());
                assertTrue("Explorer entries must use bottom dividers instead of outlined cards",
                    folder.getBackground() instanceof LayerDrawable);
                LayerDrawable layers = (LayerDrawable) folder.getBackground();
                assertEquals(2, layers.getNumberOfLayers());
                assertTrue(layers.getDrawable(1) instanceof ColorDrawable);
                assertEquals(NegrescoTheme.BORDER,
                    ((ColorDrawable) layers.getDrawable(1)).getColor());
                assertEquals(Gravity.BOTTOM | Gravity.FILL_HORIZONTAL,
                    layers.getLayerGravity(1));
                assertEquals(NegrescoTheme.dp(activity, 1), layers.getLayerHeight(1));
                assertEquals("Rows must meet edge to edge without inter-card gaps", 0,
                    ((LinearLayout.LayoutParams) folder.getLayoutParams()).bottomMargin);
                assertTrue("Tap height must remain at least 58dp",
                    folder.getMinimumHeight() >= NegrescoTheme.dp(activity, 58));
                assertTrue("Files need an independent native icon",
                    folder.getChildAt(0) instanceof ImageView);
                assertEquals("Abrir pasta assets/", folder.getContentDescription());
                assertTrue(folder.performClick());
                assertEquals(1, opened.get());
                View options = descendant(folder, "Opções de assets/");
                assertNotNull(options);
                assertEquals("File menu hitbox must be at least 48dp",
                    NegrescoTheme.dp(activity, 48), options.getLayoutParams().width);
                assertEquals("File menu height must be at least 48dp",
                    NegrescoTheme.dp(activity, 48), options.getLayoutParams().height);
                AccessibilityNodeInfo optionsNode = options.createAccessibilityNodeInfo();
                assertNotNull(optionsNode);
                assertEquals("Overflow must be announced as a native button",
                    android.widget.Button.class.getName(),
                    optionsNode.getClassName().toString());
                assertEquals("Opções de assets/",
                    optionsNode.getContentDescription().toString());
                assertTrue("Overflow must be a separate clickable action",
                    optionsNode.isClickable());
                optionsNode.recycle();
                assertTrue(options.performClick());
                assertEquals(1, optionsOpened.get());
                assertEquals("Opening options must not enter a folder",
                    1, opened.get());

                P7ExplorerEntryRow edited = new P7ExplorerEntryRow(activity,
                    "AndroidManifest.xml", "XML • 1.5 KB • ALTERADO",
                    false, true, v -> opened.incrementAndGet(),
                    v -> optionsOpened.incrementAndGet());
                assertEquals("Abrir arquivo AndroidManifest.xml, alterado",
                    edited.getContentDescription());
                assertTrue(edited.getChildAt(1) instanceof LinearLayout);
                LinearLayout labels = (LinearLayout) edited.getChildAt(1);
                assertTrue(((TextView) labels.getChildAt(0))
                    .getText().toString().contains("AndroidManifest.xml"));
                assertTrue(((TextView) labels.getChildAt(1))
                    .getText().toString().contains("ALTERADO"));
                View fileOptions = descendant(edited, "Opções de AndroidManifest.xml");
                assertNotNull("Edited file also needs an independent overflow", fileOptions);
                AccessibilityNodeInfo fileNode = fileOptions.createAccessibilityNodeInfo();
                assertEquals(android.widget.Button.class.getName(),
                    fileNode.getClassName().toString());
                assertTrue(fileNode.isClickable());
                fileNode.recycle();
                assertTrue(fileOptions.performClick());
                assertEquals("File overflow must not open the file", 1, opened.get());
                assertEquals(2, optionsOpened.get());
            });
        }
    }
}
