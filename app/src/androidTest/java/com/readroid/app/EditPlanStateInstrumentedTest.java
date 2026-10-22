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
