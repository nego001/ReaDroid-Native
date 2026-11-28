package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.io.InterruptedIOException;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ExportSessionGuardInstrumentedTest {
    @Test public void newlyCapturedSessionIsActive() throws Exception {
        ExportSessionGuard sessions = new ExportSessionGuard();
        ExportSessionGuard.Token token = sessions.begin();
        token.requireActive();
        assertTrue(token.isActive());
    }

    @Test public void startingNewProjectInvalidatesPreviousExport() throws Exception {
        ExportSessionGuard sessions = new ExportSessionGuard();
        ExportSessionGuard.Token old = sessions.begin();
        sessions.invalidate();
        assertFalse(old.isActive());
        try {
            old.requireActive();
            fail("Old project export cannot remain active");
        } catch (InterruptedIOException expected) {
            assertTrue(expected.getMessage().contains("cancelada"));
        }
    }

    @Test public void secondExportSupersedesFirst() throws Exception {
        ExportSessionGuard sessions = new ExportSessionGuard();
        ExportSessionGuard.Token first = sessions.begin();
        ExportSessionGuard.Token second = sessions.begin();
        assertFalse(first.isActive());
        second.requireActive();
    }

    @Test public void cancelledTokenNeverReactivatesAfterNewProjects() throws Exception {
        ExportSessionGuard sessions = new ExportSessionGuard();
        ExportSessionGuard.Token oldest = sessions.begin();
        for (int i = 0; i < 8; i++) {
            sessions.invalidate();
            sessions.begin();
        }
        assertFalse(oldest.isActive());
    }

    @Test public void interruptedWorkerIsRejectedEvenWithMatchingGeneration()
            throws Exception {
        ExportSessionGuard.Token token = new ExportSessionGuard().begin();
        Thread.currentThread().interrupt();
        try {
            token.requireActive();
            fail("Interrupted worker may not export");
        } catch (InterruptedIOException expected) {
            assertTrue(expected.getMessage().contains("cancelada"));
        } finally {
            Thread.interrupted();
        }
    }
}
