package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import static org.junit.Assert.*;

/** Basic edit-state regression, separate from the deferred dialog redesign. */
@RunWith(AndroidJUnit4.class)
public final class EditPlanStateInstrumentedTest {
    private static final String PATH = "assets/teste_recuperacao.txt";

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

    @Test public void invalidPathCannotEnterPlanEvenIfTextIsUnchanged() {
        EditPlan plan = new EditPlan();
        try {
            plan.applyTextEdit("../segredo.txt", "original", "original");
            fail("Unsafe path cannot bypass validation");
        } catch (IllegalArgumentException expected) {
            assertEquals(0, plan.size());
        }
    }
}
