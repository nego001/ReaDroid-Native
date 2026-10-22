package com.readroid.app;

import android.net.Uri;
import android.content.Context;
import android.content.SharedPreferences;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Persistent history may only show SAF documents with real read grants. */
@RunWith(AndroidJUnit4.class)
public final class P7ProjectHistoryInstrumentedTest {
    @Test public void noForgedOrMalformedDocumentReferencesReachTheHistory() throws Exception {
        Set<String> allowed = new HashSet<>(Arrays.asList(
            "content://fixture.provider/document/first",
            "content://fixture.provider/document/second",
            "file:///private/app.apk"));
        JSONArray fixture = new JSONArray();
        fixture.put(new JSONObject().put("uri", "content://fixture.provider/document/first")
            .put("name", "Primeiro.apk").put("package", "com.test.first")
            .put("openedAt", 1234));
        fixture.put(new JSONObject().put("uri", "content://fixture.provider/document/first")
            .put("name", "Duplicado.apk"));
        fixture.put(new JSONObject().put("uri", "file:///private/app.apk")
            .put("name", "Arquivo inseguro"));
        fixture.put(new JSONObject().put("uri", "content://not.allowed/document/third")
            .put("name", "Sem permissão.apk"));
        fixture.put(new JSONObject().put("uri", "content://fixture.provider/document/second")
            .put("name", "Segundo.apk\nlinha"));
        List<P7ProjectHistory.Entry> read =
            P7ProjectHistory.decode(fixture.toString(), allowed);
        assertEquals(2, read.size());
        assertEquals("Primeiro.apk", read.get(0).name);
        assertEquals("Segundo.apk linha", read.get(1).name);
        assertEquals("com.test.first", read.get(0).packageName);
        assertTrue(P7ProjectHistory.decode("{", allowed).isEmpty());
        assertFalse(P7ProjectHistory.record(
            InstrumentationRegistry.getInstrumentation().getTargetContext(),
            Uri.parse("content://ungranted.example/document/test"), "com.fake"));
    }

    @Test public void clearHistoryRunsAfterPendingMetadataWorkOnSameExecutor()
            throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        SharedPreferences prefs = context.getSharedPreferences(
            "p7_recent_apks", Context.MODE_PRIVATE);
        String original = prefs.getString("entries", null);
        CountDownLatch workerStarted = new CountDownLatch(1);
        CountDownLatch releaseWorker = new CountDownLatch(1);
        CountDownLatch completed = new CountDownLatch(1);
        try {
            try (ActivityScenario<MainActivity> scenario =
                    ActivityScenario.launch(MainActivity.class)) {
                scenario.onActivity(activity -> {
                    try {
                        assertTrue(prefs.edit().putString("entries",
                            "queued-history-fixture").commit());
                        Field field = MainActivity.class.getDeclaredField("executor");
                        field.setAccessible(true);
                        ExecutorService executor = (ExecutorService) field.get(activity);
                        executor.execute(() -> {
                            workerStarted.countDown();
                            try {
                                releaseWorker.await(10, TimeUnit.SECONDS);
                            } catch (InterruptedException interrupted) {
                                Thread.currentThread().interrupt();
                            }
                        });
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                assertTrue("Metadata worker did not start",
                    workerStarted.await(5, TimeUnit.SECONDS));
                scenario.onActivity(activity -> {
                    try {
                        Method mutate = MainActivity.class.getDeclaredMethod(
                            "mutateRecentProjectHistory", Uri.class);
                        mutate.setAccessible(true);
                        mutate.invoke(activity, (Object) null);
                        Field field = MainActivity.class.getDeclaredField("executor");
                        field.setAccessible(true);
                        ((ExecutorService) field.get(activity))
                            .execute(completed::countDown);
                        assertTrue("Clear unexpectedly ran on the UI thread",
                            prefs.contains("entries"));
                    } catch (Exception error) { throw new AssertionError(error); }
                });
                releaseWorker.countDown();
                assertTrue("Queued clear and prune never finished",
                    completed.await(15, TimeUnit.SECONDS));
                assertFalse("Recent history reappeared after clear",
                    prefs.contains("entries"));
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    assertNotNull("Clearing must leave the Activity usable",
                        activity.getWindow().getDecorView());
                });
            }
        } finally {
            releaseWorker.countDown();
            SharedPreferences.Editor restoration = prefs.edit();
            if (original == null) restoration.remove("entries");
            else restoration.putString("entries", original);
            assertTrue(restoration.commit());
        }
    }

    private static View findDescription(View node, String text) {
        if (text.equals(node.getContentDescription())) return node;
        if (node instanceof ViewGroup) {
            ViewGroup parent = (ViewGroup) node;
            for (int i = 0; i < parent.getChildCount(); i++) {
                View result = findDescription(parent.getChildAt(i), text);
                if (result != null) return result;
            }
        }
        return null;
    }

    private static boolean hasText(View node, String value) {
        if (node instanceof TextView
                && value.equals(((TextView) node).getText().toString())) return true;
        if (node instanceof ViewGroup) {
            ViewGroup p = (ViewGroup) node;
            for (int i = 0; i < p.getChildCount(); i++)
                if (hasText(p.getChildAt(i), value)) return true;
        }
        return false;
    }

    @Test public void homeShowsThreeRealRowsAndCountsAllAccessibleProjects() {
        try (ActivityScenario<MainActivity> scenario =
                ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a -> {
                AtomicInteger opened = new AtomicInteger(-1);
                AtomicInteger expanded = new AtomicInteger(0);
                P7HomeOverview home = new P7HomeOverview(a, v -> {});
                home.setHistoryCallbacks(entry -> opened.set(
                    Integer.parseInt(entry.uri.getLastPathSegment())),
                    v -> expanded.incrementAndGet());
                List<P7ProjectHistory.Entry> entries = new ArrayList<>();
                for (int i = 0; i < 4; i++)
                    entries.add(new P7ProjectHistory.Entry(
                        Uri.parse("content://test.provider/document/" + i),
                        "Arquivo" + i + ".apk", "com.example." + i, 1000L + i));
                home.setRecentProjects(entries, null);
                a.setContentView(home);
                assertTrue(hasText(home, "4"));
                assertTrue(hasText(home, "Arquivo0.apk"));
                assertTrue(hasText(home, "Arquivo1.apk"));
                assertTrue(hasText(home, "Arquivo2.apk"));
                assertFalse(hasText(home, "Arquivo3.apk"));
                View row = findDescription(home,
                    "Abrir projeto Arquivo1.apk, com.example.1");
                assertNotNull(row);
                assertTrue(row.performClick());
                assertEquals(1, opened.get());
                View more = findDescription(home, "Mais opções de Arquivo1.apk");
                assertNotNull("Reference projects require a contextual ⋮ menu", more);
                assertTrue("Context actions must be accessible", more.isClickable());
                assertFalse(P7ProjectHistory.forget(a,
                    Uri.parse("content://ungranted.example/document/1")));
                View all = findDescription(home, "Ver todos os projetos recentes");
                assertNotNull(all);
                assertTrue(all.performClick());
                assertEquals(1, expanded.get());
            });
        }
    }
}
