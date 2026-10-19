package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.LinearLayout;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

/** Verify that each bottom tab is one reachable, accurately described action. */
@RunWith(AndroidJUnit4.class)
public final class NavigationAccessibilityInstrumentedTest {
    private static View find(View view, String label) {
        if (view.getContentDescription() != null
            && view.getContentDescription().toString().startsWith("Seção " + label))
            return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View child = find(group.getChildAt(i), label);
                if (child != null) return child;
            }
        }
        return null;
    }

    @Test public void tabsExposeButtonRolesAndReflectSelection() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                String[] tabs = {"Início", "Arquivos", "Construir", "Segurança", "IA"};
                for (String name : tabs) {
                    View tab = find(root, name);
                    assertNotNull("Missing tab " + name, tab);
                    assertTrue(tab.isFocusable());
                    assertTrue(tab.isClickable());
                    assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_YES,
                        tab.getImportantForAccessibility());
                    AccessibilityNodeInfo info = tab.createAccessibilityNodeInfo();
                    assertEquals(Button.class.getName(), info.getClassName().toString());
                    assertTrue(info.getContentDescription().toString().startsWith("Seção " + name));
                    assertEquals("Início".equals(name), tab.isSelected());
                    info.recycle();
                }
                View files = find(root, "Arquivos");
                assertNotNull(files);
                assertTrue(files.performClick());
                assertTrue(files.isSelected());
                assertTrue(files.getContentDescription().toString().contains("selecionada"));
                assertFalse(find(root, "Início").isSelected());
                assertTrue(find(root, "Início").performClick());
                assertTrue(find(root, "Início").isSelected());
            });
        }
    }

    @Test public void iconsAreDecorativeAndNotDuplicateTalkBackStops() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View navigation = find(root, "Arquivos");
                assertNotNull(navigation);
                assertTrue(navigation instanceof ViewGroup);
                ViewGroup group = (ViewGroup) navigation;
                assertTrue(group.getChildCount() >= 2);
                assertTrue(group.getChildAt(0) instanceof NavGlyph);
                assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                    group.getChildAt(0).getImportantForAccessibility());
                assertEquals(View.IMPORTANT_FOR_ACCESSIBILITY_NO,
                    group.getChildAt(1).getImportantForAccessibility());
            });
        }
    }
}
