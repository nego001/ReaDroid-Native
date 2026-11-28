package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import java.util.Arrays;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

/** Basic edit-state regression, separate from the deferred dialog redesign. */
@RunWith(AndroidJUnit4.class)
public final class EditPlanStateInstrumentedTest {
    private static final String PATH = "assets/teste_recuperacao.txt";

    @Test public void oldEditorCannotWriteIntoNewApkAfterProjectSwitch()
            throws Exception {
        try (androidx.test.core.app.ActivityScenario<MainActivity> scenario =
                androidx.test.core.app.ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                java.io.File first = null, second = null;
                try {
                    first = java.io.File.createTempFile("edit_source_a_", ".apk",
                        activity.getCacheDir());
                    second = java.io.File.createTempFile("edit_source_b_", ".apk",
                        activity.getCacheDir());
                    ExplorerView explorer = new ExplorerView(activity,
                        new android.widget.LinearLayout(activity));
                    explorer.setFiles(new org.json.JSONArray(), first);
                    ExplorerView.EditSession old = explorer.captureEditSession();
                    assertTrue(explorer.isCurrentEditSession(old));
                    assertEquals(EditPlan.EditResult.ADDED,
                        explorer.applyTextEditForSession(old, PATH, "antes", "editado A"));
                    // Mirrors MainActivity's accepted import: clear the old
                    // edit plan, then replace the Explorer's project binding.
                    explorer.getEditPlan().clear();
                    explorer.setFiles(new org.json.JSONArray(), second);
                    assertFalse("Old editor must be invalid after import",
                        explorer.isCurrentEditSession(old));
                    try {
                        explorer.applyTextEditForSession(old, PATH,
                            "antes", "edição atrasada de A");
                        fail("A former APK cannot write into the new APK edit plan");
                    } catch (IllegalStateException expected) {
                        assertTrue(expected.getMessage().contains("outro APK"));
                    }
                    assertEquals(0, explorer.getEditPlan().size());
                    ExplorerView.EditSession current = explorer.captureEditSession();
                    assertEquals(EditPlan.EditResult.ADDED,
                        explorer.applyTextEditForSession(current, PATH,
                            "original B", "mudança B"));
                    assertEquals("mudança B", explorer.getEditPlan().get(PATH));
                    // Even rebinding the same file must invalidate a dialog
                    // from the old session; path equality is insufficient.
                    explorer.setFiles(new org.json.JSONArray(), second);
                    assertFalse(explorer.isCurrentEditSession(current));
                    try {
                        explorer.applyTextEditForSession(current, PATH,
                            "original B", "texto antigo");
                        fail("Rebound project must invalidate old editor");
                    } catch (IllegalStateException expected) {
                        assertEquals("mudança B", explorer.getEditPlan().get(PATH));
                    }
                } catch (Exception problem) {
                    throw new AssertionError(problem);
                } finally {
                    if (first != null) first.delete();
                    if (second != null) second.delete();
                }
            });
        }
    }

    @Test public void failedCandidateCannotInvalidateActiveEditSession()
            throws Exception {
        try (androidx.test.core.app.ActivityScenario<MainActivity> scenario =
                androidx.test.core.app.ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                java.io.File active = null;
                try {
                    active = java.io.File.createTempFile("edit_active_", ".apk",
                        activity.getCacheDir());
                    ExplorerView explorer = new ExplorerView(activity,
                        new android.widget.LinearLayout(activity));
                    explorer.setFiles(new org.json.JSONArray(), active);
                    ExplorerView.EditSession edit = explorer.captureEditSession();
                    // A rejected candidate never calls setFiles() in
                    // MainActivity's transactional import path.
                    assertTrue(explorer.isCurrentEditSession(edit));
                    assertEquals(EditPlan.EditResult.ADDED,
                        explorer.applyTextEditForSession(edit, PATH,
                            "original", "preservado"));
                    assertEquals("preservado", explorer.getEditPlan().get(PATH));
                    explorer.setFiles(null, null);
                    assertFalse(explorer.isCurrentEditSession(edit));
                    try {
                        explorer.applyTextEditForSession(edit, PATH,
                            "original", "não autorizado");
                        fail("Clearing the workspace must invalidate editors");
                    } catch (IllegalStateException expected) {
                        assertEquals("preservado", explorer.getEditPlan().get(PATH));
                    }
                } catch (Exception problem) {
                    throw new AssertionError(problem);
                } finally {
                    if (active != null) active.delete();
                }
            });
        }
    }

    @Test public void stalePreviewAndTechnicalResultsNeverDisplayAfterApkSwitch()
            throws Exception {
        try (androidx.test.core.app.ActivityScenario<MainActivity> scenario =
                androidx.test.core.app.ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                java.io.File first = null, second = null;
                try {
                    first = java.io.File.createTempFile("session_preview_a_", ".apk",
                        activity.getCacheDir());
                    second = java.io.File.createTempFile("session_preview_b_", ".apk",
                        activity.getCacheDir());
                    ExplorerView explorer = new ExplorerView(activity,
                        new android.widget.LinearLayout(activity));
                    explorer.setFiles(new org.json.JSONArray(), first);
                    ExplorerView.EditSession oldPreview = explorer.captureEditSession();
                    java.util.concurrent.atomic.AtomicInteger deliveries =
                        new java.util.concurrent.atomic.AtomicInteger();
                    assertTrue(explorer.showForCurrentSession(oldPreview,
                        deliveries::incrementAndGet));
                    assertEquals(1, deliveries.get());
                    explorer.setFiles(new org.json.JSONArray(), second);
                    assertFalse("Old APK preview/metadata must not be displayed",
                        explorer.showForCurrentSession(oldPreview,
                            deliveries::incrementAndGet));
                    assertEquals("No stale callbacks may run", 1, deliveries.get());
                    ExplorerView.EditSession now = explorer.captureEditSession();
                    assertTrue("Current APK should still show its own results",
                        explorer.showForCurrentSession(now,
                            deliveries::incrementAndGet));
                    assertEquals(2, deliveries.get());
                    explorer.setFiles(null, null);
                    assertFalse("Clearing project must cancel pending result",
                        explorer.showForCurrentSession(now,
                            deliveries::incrementAndGet));
                    assertEquals(2, deliveries.get());
                } catch (Exception problem) {
                    throw new AssertionError(problem);
                } finally {
                    if (first != null) first.delete();
                    if (second != null) second.delete();
                }
            });
        }
    }

    @Test public void rejectedRecoveryMustNotErasePendingEdits() {
        EditPlan plan = new EditPlan();
        plan.addTextReplacement(PATH, "minha edição atual");
        java.util.Map<String, String> invalid = new java.util.LinkedHashMap<>();
        invalid.put("assets/nova.txt", "segura");
        invalid.put("../perigoso.json", "inválida");
        try {
            plan.replaceAllValidated(invalid);
            fail("One malformed recovery entry must invalidate the entire replacement");
        } catch (IllegalArgumentException expected) {
            assertEquals(1, plan.size());
            assertEquals("minha edição atual", plan.get(PATH));
            assertFalse(plan.contains("assets/nova.txt"));
        }
        try {
            plan.replaceAllValidated(java.util.Collections.emptyMap());
            fail("Empty recovery must not clear the plan");
        } catch (IllegalArgumentException expected) {
            assertEquals("minha edição atual", plan.get(PATH));
        }
        java.util.Map<String, String> valid = new java.util.LinkedHashMap<>();
        valid.put("assets/recuperado.txt", "conteúdo recuperado");
        plan.replaceAllValidated(valid);
        assertEquals(1, plan.size());
        assertFalse(plan.contains(PATH));
        assertEquals("conteúdo recuperado", plan.get("assets/recuperado.txt"));
    }

    @Test public void staleRecoveryConfirmationCannotReplaceNewProjectPlan()
            throws Exception {
        try (androidx.test.core.app.ActivityScenario<MainActivity> scenario =
                androidx.test.core.app.ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                java.io.File first = null, second = null;
                try {
                    first = java.io.File.createTempFile("recovery_project_a_", ".apk",
                        activity.getCacheDir());
                    second = java.io.File.createTempFile("recovery_project_b_", ".apk",
                        activity.getCacheDir());
                    ExplorerView explorer = new ExplorerView(activity,
                        new android.widget.LinearLayout(activity));
                    explorer.setFiles(new org.json.JSONArray(), first);
                    ExplorerView.EditSession old = explorer.captureEditSession();
                    java.util.Map<String, String> recovered = new java.util.LinkedHashMap<>();
                    recovered.put("assets/old.txt", "cópia antiga");
                    explorer.setFiles(new org.json.JSONArray(), second);
                    ExplorerView.EditSession current = explorer.captureEditSession();
                    explorer.applyTextEditForSession(current, PATH,
                        "original B", "edição de B");
                    try {
                        explorer.restoreEditPlanForSession(old, recovered);
                        fail("Recovery from A cannot overwrite edits in B");
                    } catch (IllegalStateException expected) {
                        assertTrue(expected.getMessage().contains("outro APK"));
                    }
                    assertEquals("edição de B", explorer.getEditPlan().get(PATH));
                    assertFalse(explorer.getEditPlan().contains("assets/old.txt"));
                    explorer.restoreEditPlanForSession(current, recovered);
                    assertEquals(1, explorer.getEditPlan().size());
                    assertEquals("cópia antiga",
                        explorer.getEditPlan().get("assets/old.txt"));
                    assertFalse(explorer.getEditPlan().contains(PATH));
                    // A same-file rebind is another project generation: a
                    // previously displayed recovery confirmation is stale.
                    explorer.setFiles(new org.json.JSONArray(), second);
                    explorer.applyTextEditForSession(explorer.captureEditSession(),
                        PATH, "original", "edição posterior");
                    try {
                        explorer.restoreEditPlanForSession(current, recovered);
                        fail("Rebound same-file recovery must not mutate a new session");
                    } catch (IllegalStateException expected) {
                        assertEquals("edição posterior",
                            explorer.getEditPlan().get(PATH));
                    }
                } catch (Exception problem) {
                    throw new AssertionError(problem);
                } finally {
                    if (first != null) first.delete();
                    if (second != null) second.delete();
                }
            });
        }
    }

    @Test public void malformedRecoveryOnCurrentSessionKeepsCurrentEdits()
            throws Exception {
        try (androidx.test.core.app.ActivityScenario<MainActivity> scenario =
                androidx.test.core.app.ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(activity -> {
                java.io.File active = null;
                try {
                    active = java.io.File.createTempFile("recovery_current_", ".apk",
                        activity.getCacheDir());
                    ExplorerView explorer = new ExplorerView(activity,
                        new android.widget.LinearLayout(activity));
                    explorer.setFiles(new org.json.JSONArray(), active);
                    ExplorerView.EditSession session = explorer.captureEditSession();
                    explorer.applyTextEditForSession(session, PATH, "original",
                        "manter meu trabalho");
                    java.util.Map<String, String> malformed =
                        new java.util.LinkedHashMap<>();
                    malformed.put("assets/first.txt", "válido");
                    malformed.put("assets/second.txt",
                        "surrogate inválido " + (char) 0xD83D);
                    try {
                        explorer.restoreEditPlanForSession(session, malformed);
                        fail("Malformed Unicode cannot partially apply recovery");
                    } catch (IllegalArgumentException expected) {
                        assertEquals("manter meu trabalho",
                            explorer.getEditPlan().get(PATH));
                        assertFalse(explorer.getEditPlan().contains("assets/first.txt"));
                    }
                } catch (Exception problem) {
                    throw new AssertionError(problem);
                } finally {
                    if (active != null) active.delete();
                }
            });
        }
    }

    @Test public void unchangedOriginalDoesNotCreateFakeSuccess() {
        EditPlan plan = new EditPlan();
        assertEquals(EditPlan.EditResult.UNCHANGED,
            plan.applyTextEdit(PATH, "original", "original"));
        assertEquals(0, plan.size());
        assertFalse(plan.contains(PATH));
    }

    @Test public void changedTextCreatesExactlyOneEdit() {
        EditPlan plan = new EditPlan();
        assertEquals(EditPlan.EditResult.ADDED,
            plan.applyTextEdit(PATH, "original", "alterado"));
        assertEquals(1, plan.size());
        assertEquals("alterado", plan.get(PATH));
        assertEquals(EditPlan.EditResult.UNCHANGED,
            plan.applyTextEdit(PATH, "original", "alterado"));
        assertEquals(1, plan.size());
    }

    @Test public void editingAgainUpdatesInsteadOfDuplicating() {
        EditPlan plan = new EditPlan();
        plan.applyTextEdit(PATH, "original", "versão 1");
        assertEquals(EditPlan.EditResult.UPDATED,
            plan.applyTextEdit(PATH, "original", "versão 2"));
        assertEquals(1, plan.size());
        assertEquals("versão 2", plan.get(PATH));
    }

    @Test public void revertingToOriginalRemovesOnlyThisEdit() {
        EditPlan plan = new EditPlan();
        plan.applyTextEdit(PATH, "original", "alterado");
        plan.applyTextEdit("assets/outro.json", "{}", "{\"ok\":true}");
        assertEquals(EditPlan.EditResult.REMOVED,
            plan.applyTextEdit(PATH, "original", "original"));
        assertEquals(1, plan.size());
        assertFalse(plan.contains(PATH));
        assertTrue(plan.contains("assets/outro.json"));
        assertEquals(EditPlan.EditResult.UNCHANGED,
            plan.applyTextEdit(PATH, "original", "original"));
    }

    private static String filled(char glyph, int count) {
        char[] chars = new char[count];
        Arrays.fill(chars, glyph);
        return new String(chars);
    }

    @Test public void utf8SizeLimitAllowsExactBoundaryAndRejectsOneExtraByte() {
        EditPlan plan = new EditPlan();
        String atLimit = filled('é', 65536); // 65536 * 2 = 131072 UTF-8 bytes
        plan.addTextReplacement(PATH, atLimit);
        assertEquals(atLimit, plan.get(PATH));
        assertEquals(1, plan.size());
        try {
            plan.addTextReplacement(PATH, atLimit + "a");
            fail("Must reject 128 KiB plus one byte");
        } catch (IllegalArgumentException expected) {
            assertEquals("Rejected overwrite must keep previous valid edit",
                atLimit, plan.get(PATH));
            assertEquals(1, plan.size());
        }
    }

    @Test public void tooManyUtf8BytesNeverCreatesEditOrChangesExistingPlan() {
        EditPlan plan = new EditPlan();
        plan.addTextReplacement(PATH, "preservar alteração");
        String multiByte = filled('界', 44000); // 44000 UTF-8 chars = 132000 bytes
        assertTrue("Fixture must be below the old character count",
            multiByte.length() < 131072);
        try {
            plan.applyTextEdit("assets/novo.json", multiByte, multiByte);
            fail("Unchanged Unicode text cannot bypass byte-size validation");
        } catch (IllegalArgumentException expected) {
            assertEquals(1, plan.size());
            assertEquals("preservar alteração", plan.get(PATH));
            assertFalse(plan.contains("assets/novo.json"));
        }
        try {
            plan.applyTextEdit(PATH, "original", multiByte);
            fail("Oversized Unicode update must not overwrite a valid change");
        } catch (IllegalArgumentException expected) {
            assertEquals("preservar alteração", plan.get(PATH));
            assertEquals(1, plan.size());
        }
    }

    @Test public void supplementaryUnicodeFitsExactUtf8Boundary() {
        EditPlan plan = new EditPlan();
        String emoji = new String(Character.toChars(0x1F9EA));
        StringBuilder content = new StringBuilder(65536);
        for (int i = 0; i < 32768; i++) content.append(emoji);
        String atLimit = content.toString();
        assertEquals(131072, atLimit.getBytes(java.nio.charset.StandardCharsets.UTF_8).length);
        plan.addTextReplacement(PATH, atLimit);
        assertEquals(atLimit, plan.get(PATH));
        try {
            plan.addTextReplacement(PATH, atLimit + "a");
            fail("Extra UTF-8 byte should be rejected");
        } catch (IllegalArgumentException expected) {
            assertEquals(atLimit, plan.get(PATH));
        }
    }

    @Test public void orphanSurrogatesCannotCorruptExistingEdit() {
        EditPlan plan = new EditPlan();
        plan.addTextReplacement(PATH, "edição íntegra");
        String high = "abc" + (char) 0xD83D;
        String low = "abc" + (char) 0xDE00;
        for (String invalid : new String[]{high, low}) {
            try {
                plan.addTextReplacement(PATH, invalid);
                fail("Orphan surrogate must never be silently encoded as '?'");
            } catch (IllegalArgumentException expected) {
                assertEquals("edição íntegra", plan.get(PATH));
            }
            try {
                plan.applyTextEdit("assets/new.txt", invalid, invalid);
                fail("Unchanged malformed text must be rejected too");
            } catch (IllegalArgumentException expected) {
                assertFalse(plan.contains("assets/new.txt"));
            }
        }
        assertEquals(1, plan.size());
    }

    @Test public void invalidPathCannotEnterPlanEvenIfTextIsUnchanged() {
        EditPlan plan = new EditPlan();
        try {
            plan.applyTextEdit("../segredo.txt", "original", "original");
            fail("Unsafe path cannot bypass validation");
        } catch (IllegalArgumentException expected) {
            assertEquals(0, plan.size());
        }
    }

    @Test public void f148RevisionAdvancesOnlyForActualContentChanges() {
        EditPlan p = new EditPlan();
        long start = p.revision();
        p.clear();
        assertFalse(p.remove(PATH));
        assertEquals(start, p.revision());
        p.addTextReplacement(PATH, "A");
        long a = p.revision();
        assertTrue(a > start);
        p.addTextReplacement(PATH, "A");
        assertEquals(EditPlan.EditResult.UNCHANGED, p.applyTextEdit(PATH, "original", "A"));
        assertEquals(a, p.revision());
        assertEquals(EditPlan.EditResult.UPDATED, p.applyTextEdit(PATH, "original", "B"));
        long b = p.revision();
        assertTrue(b > a);
        p.addTextReplacement(PATH, "A");
        long undo = p.revision();
        assertTrue(undo > b);
        assertEquals("A", p.get(PATH));
        assertEquals(EditPlan.EditResult.REMOVED, p.applyTextEdit(PATH, "original", "original"));
        assertTrue(p.revision() > undo);
        long empty = p.revision();
        assertEquals(EditPlan.EditResult.UNCHANGED, p.applyTextEdit(PATH, "original", "original"));
        assertEquals(empty, p.revision());
    }

    @Test public void f148ValidatedReplacementAndClearTrackRevision() {
        EditPlan p = new EditPlan();
        p.addTextReplacement(PATH, "A");
        long a = p.revision();
        p.replaceAllValidated(java.util.Collections.singletonMap(PATH, "A"));
        assertEquals(a, p.revision());
        try {
            p.replaceAllValidated(java.util.Collections.singletonMap("../bad.txt", "B"));
            fail("Invalid recovery must not mutate revision");
        } catch (IllegalArgumentException expected) {
            assertEquals(a, p.revision());
            assertEquals("A", p.get(PATH));
        }
        p.replaceAllValidated(java.util.Collections.singletonMap(PATH, "B"));
        long b = p.revision();
        assertTrue(b > a);
        p.clear();
        assertTrue(p.revision() > b);
        long cleared = p.revision();
        p.clear();
        assertEquals(cleared, p.revision());
    }
}
