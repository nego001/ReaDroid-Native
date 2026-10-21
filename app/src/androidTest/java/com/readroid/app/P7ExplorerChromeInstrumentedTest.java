package com.readroid.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** P7 explorer UI contract. Uses only synthetic paths and no real APK content. */
@RunWith(AndroidJUnit4.class)
public final class P7ExplorerChromeInstrumentedTest {
    private static TextView find(View node, String exact) {
        if (node instanceof TextView
                && exact.equals(((TextView) node).getText().toString()))
            return (TextView) node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                TextView candidate = find(group.getChildAt(i), exact);
                if (candidate != null) return candidate;
            }
        }
        return null;
    }

    private static TextView findPrefix(View node, String prefix) {
        if (node instanceof TextView
                && ((TextView) node).getText().toString().startsWith(prefix))
            return (TextView) node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                TextView candidate = findPrefix(group.getChildAt(i), prefix);
                if (candidate != null) return candidate;
            }
        }
        return null;
    }

    private static View byDescription(View node, String expected) {
        if (expected.equals(node.getContentDescription())) return node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = byDescription(group.getChildAt(i), expected);
                if (found != null) return found;
            }
        }
        return null;
    }

    @Test public void projectCardChipsAndBreadcrumbsRespectRealBrowserState() throws Exception {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    LinearLayout root = new LinearLayout(activity);
                    root.setOrientation(LinearLayout.VERTICAL);
                    activity.setContentView(root);
                    ExplorerView explorer = new ExplorerView(activity, root);
                    AtomicInteger exited = new AtomicInteger();
                    AtomicInteger opened = new AtomicInteger();
                    AtomicInteger plans = new AtomicInteger();
                    explorer.setNavigationActions(exited::incrementAndGet,
                        opened::incrementAndGet, plans::incrementAndGet);
                    View backButton = byDescription(root, "Voltar no Explorador");
                    View menu = byDescription(root, "Mais opções do Explorador");
                    View edits = byDescription(root, "Abrir plano de edição");
                    View advanced = byDescription(root, "Abrir filtros avançados");
                    assertNotNull("Reference back button missing", backButton);
                    assertNotNull("Reference overflow menu missing", menu);
                    assertNotNull("Reference edit plan chip missing", edits);
                    assertNotNull("Advanced filters must share the chip row", advanced);
                    int touch = NegrescoTheme.dp(activity, 48);
                    assertTrue("Explorer back hitbox too narrow",
                        backButton.getLayoutParams().width >= touch);
                    assertTrue("Explorer back hitbox too short",
                        backButton.getLayoutParams().height >= touch);
                    assertTrue("Explorer menu hitbox too narrow",
                        menu.getLayoutParams().width >= touch);
                    assertTrue("Explorer menu hitbox too short",
                        menu.getLayoutParams().height >= touch);
                    assertTrue("Advanced filter hitbox too narrow",
                        advanced.getLayoutParams().width >= touch);
                    assertTrue("Advanced filter hitbox too short",
                        advanced.getLayoutParams().height >= touch);
                    assertTrue(backButton.performClick());
                    assertEquals(1, exited.get());
                    assertTrue(edits.performClick());
                    assertEquals(1, plans.get());
                    JSONArray entries = new JSONArray()
                        .put(new JSONObject().put("path", "assets/a.txt")
                            .put("sizeBytes", 9).put("category", "Assets"))
                        .put(new JSONObject().put("path", "lib/libdemo.so")
                            .put("sizeBytes", 10).put("category", "Bibliotecas"))
                        .put(new JSONObject().put("path", "res/icon.png")
                            .put("sizeBytes", 11).put("category", "Recursos"))
                        .put(new JSONObject().put("path", "res/config.xml")
                            .put("sizeBytes", 12).put("category", "Recursos"));
                    explorer.setFiles(entries, null);
                    explorer.setProjectSummary("com.example.synthetic", 4096);
                    assertNotNull(find(root, "Explorador de Arquivos"));
                    assertNotNull(find(root, "com.example.synthetic"));
                    assertNotNull(find(root, "0 alterações pendentes"));
                    TextView back = find(root, "← Pasta anterior");
                    assertNotNull(back);
                    assertEquals("Up button should not occupy root screen", View.GONE,
                        back.getVisibility());
                    assertNotNull(byDescription(root, "Abrir pasta lib/"));
                    assertNotNull("Screenshot must have a Smali chip", find(root, "Smali"));
                    assertNotNull("Screenshot must have an image chip", find(root, "Imagens"));
                    TextView chip = find(root, "XML");
                    assertNotNull("Reference XML filter chip is missing", chip);
                    assertTrue(chip.performClick());
                    assertNull("XML filter should hide libs",
                        byDescription(root, "Abrir pasta lib/"));
                    assertNull("XML filter should hide assets",
                        byDescription(root, "Abrir pasta assets/"));
                    View folder = byDescription(root, "Abrir pasta res/");
                    assertNotNull(folder);
                    assertTrue(folder.performClick());
                    assertEquals(View.VISIBLE, back.getVisibility());
                    assertNotNull(findPrefix(root, "config.xml"));
                    assertNull(findPrefix(root, "icon.png"));
                    assertEquals("res/", explorer.snapshotBrowseState().folder);
                    TextView rootCrumb = find(root, "APK");
                    assertNotNull(rootCrumb);
                    assertTrue(rootCrumb.performClick());
                    assertEquals("", explorer.snapshotBrowseState().folder);
                    assertNotNull(byDescription(root, "Abrir pasta res/"));
                    // The XML filter may show compiled Android XML, which is
                    // not a supported text edit. Use a known editable TXT instead.
                    TextView all = find(root, "Todos");
                    assertNotNull(all);
                    assertTrue(all.performClick());
                    assertNotNull(byDescription(root, "Abrir pasta assets/"));
                    explorer.getEditPlan().addTextReplacement("assets/a.txt", "edited");
                    explorer.refresh();
                    assertNotNull(find(root, "1 alteração pendente"));
                    assertTrue(byDescription(root, "Abrir pasta assets/").performClick());
                    assertNotNull(byDescription(root, "Abrir arquivo a.txt, alterado"));
                    View options = byDescription(root, "Opções de a.txt");
                    assertNotNull("File row must offer native three-dot options", options);
                    assertTrue(options.isClickable());
                } catch (Exception failure) {
                    throw new AssertionError(failure);
                }
            });
        }
    }
}
