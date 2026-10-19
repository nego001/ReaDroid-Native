package com.readroid.app;

import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

/**
 * Hardware-keyboard regression on a real Android window (API 29 and API 35).
 * Focus must remain distinct from the selected section. No fake TalkBack claims.
 */
@RunWith(AndroidJUnit4.class)
public final class KeyboardAndRotationInstrumentedTest {
    private static View tab(View root, String label) {
        CharSequence desc = root.getContentDescription();
        if (desc != null && desc.toString().startsWith("Seção " + label)
            && root.isClickable()) return root;
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = tab(group.getChildAt(i), label);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static View requiredTab(View root, String label) {
        View found = tab(root, label);
        assertNotNull("Missing navigation tab " + label, found);
        return found;
    }

    /**
     * A touchscreen emulator starts in touch mode: regular buttons correctly
     * refuse requestFocus() until an actual non-touch keyboard event arrives.
     * Inject a DPAD event, just as a paired physical keyboard would.
     */
    private static void beginKeyboardNavigation(ActivityScenario<MainActivity> scenario) {
        // ActivityScenario RESUMED does not guarantee the window has already
        // received focus on every emulator image. Send a bounded series of
        // actual DPAD input events and verify the app, not the launcher,
        // leaves touch mode before making keyboard assertions.
        for (int attempt = 0; attempt < 5; attempt++) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(
                KeyEvent.KEYCODE_DPAD_DOWN);
            final boolean[] keyboardMode = {false};
            scenario.onActivity(activity -> {
                View files = requiredTab(activity.getWindow().getDecorView(), "Arquivos");
                keyboardMode[0] = !files.isInTouchMode();
            });
            if (keyboardMode[0]) return;
        }
        fail("DPAD events never left touch mode after five verified attempts");
    }

    @Test public void horizontalDpadFollowsOrderWithoutChangingSelection() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            beginKeyboardNavigation(scenario);
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View build = requiredTab(root, "Construir");
                assertFalse("DPAD input must have exited touch mode", build.isInTouchMode());
                View files = requiredTab(root, "Arquivos");
                View security = requiredTab(root, "Segurança");
                assertTrue("Keyboard must be able to focus Construir", build.requestFocus());
                assertSame("DPAD left should reach Arquivos", files,
                    build.focusSearch(View.FOCUS_LEFT));
                assertSame("DPAD right should reach Segurança", security,
                    build.focusSearch(View.FOCUS_RIGHT));
                assertFalse("Keyboard focus must not silently select a section",
                    build.isSelected());
                assertTrue("Initial selected tab should still be Início",
                    requiredTab(root, "Início").isSelected());
                assertTrue(build.hasFocus());
            });
        }
    }

    @Test public void enterActivatesFocusedTabAndAnnouncesItsSelection() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            beginKeyboardNavigation(scenario);
            scenario.onActivity(activity -> {
                View files = requiredTab(activity.getWindow().getDecorView(), "Arquivos");
                assertFalse("DPAD input must have exited touch mode", files.isInTouchMode());
                assertTrue("Keyboard must focus Arquivos", files.requestFocus());
            });
            // A global instrumentation key may be swallowed by a transient
            // emulator system window. Dispatch actual down/up KeyEvents to the
            // focused production View so this test checks Android's View
            // keyboard activation rather than launcher window timing.
            scenario.onActivity(activity -> {
                View files = requiredTab(activity.getWindow().getDecorView(), "Arquivos");
                assertTrue("Focused view must still receive ENTER", files.hasFocus());
                assertTrue("ENTER down was not handled", files.dispatchKeyEvent(
                    new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER)));
                assertTrue("ENTER up was not handled", files.dispatchKeyEvent(
                    new KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER)));
            });
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View files = requiredTab(root, "Arquivos");
                assertTrue("ENTER must activate focused tab", files.isSelected());
                assertTrue("Focus should remain on activated tab", files.hasFocus());
                assertTrue(files.getContentDescription().toString().contains("selecionada"));
                AccessibilityNodeInfo info = files.createAccessibilityNodeInfo();
                try {
                    assertEquals(Button.class.getName(), info.getClassName().toString());
                    assertTrue(info.isSelected());
                } finally {
                    info.recycle();
                }
            });
        }
    }

    @Test public void rotationRecreatesActivityWithoutLosingSelectedTab() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                View security = requiredTab(activity.getWindow().getDecorView(), "Segurança");
                assertTrue(security.performClick());
                assertTrue(security.isSelected());
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                View security = requiredTab(root, "Segurança");
                assertTrue("Selected section must survive Activity recreation",
                    security.isSelected());
                assertFalse(requiredTab(root, "Início").isSelected());
                assertTrue(security.getContentDescription().toString().contains("selecionada"));
            });
        }
    }
}
