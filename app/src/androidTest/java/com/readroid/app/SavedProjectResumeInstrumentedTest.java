package com.readroid.app;

import android.net.Uri;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class SavedProjectResumeInstrumentedTest {
    private static final Uri ACCEPTED = Uri.parse(
        "content://org.example.documents/document/accepted.apk");
    private static final Uri PENDING = Uri.parse(
        "content://org.example.documents/document/pending.apk");

    @Test public void processDeathOnlyResumesAcceptedUriWithPersistedReadGrant() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            ACCEPTED, null, false, uri -> uri.equals(ACCEPTED));
        assertEquals(ACCEPTED, result.reimport);
        assertEquals(ACCEPTED, result.acceptedReference);
        assertFalse(result.requiresReselection);
    }

    @Test public void processDeathWithoutGrantRequiresPickerInsteadOfStaleImport() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            ACCEPTED, null, false, uri -> false);
        assertNull(result.reimport);
        assertNull(result.acceptedReference);
        assertTrue(result.requiresReselection);
    }

    @Test public void interruptedImportIsNeverPromotedAfterProcessDeath() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            null, PENDING, false, uri -> true);
        assertNull(result.reimport);
        assertNull(result.acceptedReference);
        assertTrue(result.requiresReselection);
    }

    @Test public void acceptedProjectWinsOverInterruptedImportAfterProcessDeath() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            ACCEPTED, PENDING, false, uri -> true);
        assertEquals(ACCEPTED, result.reimport);
        assertNotEquals(PENDING, result.reimport);
    }

    @Test public void rotationKeepsPreviousWorkspaceWhenPendingGrantExpires() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            ACCEPTED, PENDING, true, uri -> false);
        assertEquals(ACCEPTED, result.acceptedReference);
        assertNull(result.reimport);
        assertTrue(result.requiresReselection);
    }

    @Test public void rotationCanRetryStillAuthorizedPendingImport() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            ACCEPTED, PENDING, true, uri -> uri.equals(PENDING));
        assertEquals(ACCEPTED, result.acceptedReference);
        assertEquals(PENDING, result.reimport);
    }

    @Test public void confirmationRejectsRevokedGrantOrMalformedUri() {
        assertFalse(SavedProjectResume.permitted(ACCEPTED, uri -> false));
        assertFalse(SavedProjectResume.permitted(
            Uri.parse("file:///storage/emulated/0/private.apk"), uri -> true));
        assertFalse(SavedProjectResume.permitted(null, uri -> true));
        assertFalse(SavedProjectResume.permitted(ACCEPTED, uri -> {
            throw new SecurityException("Revoked while dialog open");
        }));
    }

    @Test public void noSavedProjectNeverOpensOrAsksToRestore() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            null, null, false, uri -> true);
        assertNull(result.acceptedReference);
        assertNull(result.reimport);
        assertFalse(result.requiresReselection);
    }
}
