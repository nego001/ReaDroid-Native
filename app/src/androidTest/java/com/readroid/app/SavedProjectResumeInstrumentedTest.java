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
    private static final String SHA = "0123456789abcdef0123456789abcdef"
        + "0123456789abcdef0123456789abcdef";

    @Test public void processDeathOnlyResumesAcceptedUriWithPersistedReadGrant() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            ACCEPTED, null, false, false, SHA, uri -> uri.equals(ACCEPTED));
        assertEquals(ACCEPTED, result.reimport);
        assertEquals(ACCEPTED, result.acceptedReference);
        assertEquals(SHA, result.expectedSha256);
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
            ACCEPTED, PENDING, false, false, SHA, uri -> true);
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

    @Test public void sameProcessRotationPreservesAuthorizedPendingFirstImport() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            null, PENDING, false, true, uri -> false);
        assertEquals(PENDING, result.reimport);
        assertNull(result.acceptedReference);
        assertFalse(result.requiresReselection);
    }

    @Test public void processDeathDoesNotReplayPendingEvenWithStoredGrant() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            null, PENDING, false, false, uri -> true);
        assertNull(result.reimport);
        assertTrue(result.requiresReselection);
    }

    @Test public void f120ColdResumeWithoutHashRequiresReselection() {
        SavedProjectResume.Decision d = SavedProjectResume.decide(
            ACCEPTED, null, false, false, null, uri -> true);
        assertNull(d.reimport);
        assertNull(d.expectedSha256);
        assertTrue(d.requiresReselection);
    }

    @Test public void f120InvalidOrUppercaseHashCannotAuthorizeColdResume() {
        for (String invalid : new String[]{"", "abc",
                SHA.toUpperCase(java.util.Locale.ROOT), SHA.substring(0, 63)}) {
            SavedProjectResume.Decision d = SavedProjectResume.decide(
                ACCEPTED, PENDING, false, false, invalid, uri -> true);
            assertNull(d.reimport);
            assertTrue(d.requiresReselection);
        }
    }

    @Test public void f120FingerprintDoesNotOverrideMissingGrant() {
        SavedProjectResume.Decision d = SavedProjectResume.decide(
            ACCEPTED, null, false, false, SHA, uri -> false);
        assertNull(d.reimport);
        assertTrue(d.requiresReselection);
    }

    @Test public void f120SameProcessRotationDoesNotNeedSavedHash() {
        SavedProjectResume.Decision d = SavedProjectResume.decide(
            ACCEPTED, PENDING, false, true, null, uri -> false);
        assertEquals(PENDING, d.reimport);
        assertNull(d.expectedSha256);
    }

    @Test public void f120ChangedFingerprintCannotSilentlyReplaceProject()
            throws Exception {
        String different = "ffffffffffffffffffffffffffffffff"
            + "ffffffffffffffffffffffffffffffff";
        try {
            SavedProjectResume.requireExpectedSha256(SHA, different);
            fail("A different APK under the same URI cannot be auto-accepted");
        } catch (java.io.IOException expected) {
            assertTrue(expected.getMessage().contains("mudou"));
        }
        SavedProjectResume.requireExpectedSha256(SHA, SHA);
    }

    @Test public void f120MissingObservedOrExpectedFingerprintFailsClosed()
            throws Exception {
        try {
            SavedProjectResume.requireExpectedSha256(SHA, null);
            fail("Unknown current bytes cannot be auto-accepted");
        } catch (java.io.IOException expected) {
            assertTrue(expected.getMessage().contains("mudou"));
        }
        try {
            SavedProjectResume.requireExpectedSha256(null, SHA);
            fail("Missing prior identity cannot be auto-accepted");
        } catch (java.io.IOException expected) {
            assertTrue(expected.getMessage().contains("mudou"));
        }
    }

    @Test public void noSavedProjectNeverOpensOrAsksToRestore() {
        SavedProjectResume.Decision result = SavedProjectResume.decide(
            null, null, false, uri -> true);
        assertNull(result.acceptedReference);
        assertNull(result.reimport);
        assertFalse(result.requiresReselection);
    }

    @Test public void f127ColdRestartWithRevokedGrantAndPendingImportFailsClosed() {
        SavedProjectResume.Decision denied = SavedProjectResume.decide(
            ACCEPTED, PENDING, false, false, SHA, uri -> false);
        assertNull("Cold restart must not reimport accepted project without grant",
            denied.reimport);
        assertNull(denied.acceptedReference);
        assertNull(denied.expectedSha256);
        assertTrue("User must reselect when persisted read grant is absent",
            denied.requiresReselection);

        SavedProjectResume.Decision pendingOnly = SavedProjectResume.decide(
            null, PENDING, false, false, SHA, uri -> true);
        assertNull("Unaccepted pending URI is never automatically replayed",
            pendingOnly.reimport);
        assertTrue(pendingOnly.requiresReselection);
    }
}
