package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;

import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ApkImportPreflightInstrumentedTest {
    @Test public void apkLargerThanOneGiBIsRejectedBeforeCopy() throws Exception {
        try {
            ApkImportPreflight.checkClaimedSize(1024L * 1024 * 1024 + 1,
                4L * 1024 * 1024 * 1024);
            fail("Multi-GB imports should not be enabled without infrastructure");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("multi-GB"));
        }
    }

    @Test public void claimedSizeCannotConsumeAllAvailableStorage() throws Exception {
        try {
            ApkImportPreflight.checkClaimedSize(128L * 1024 * 1024,
                160L * 1024 * 1024);
            fail("No safety reserve");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("Espaço insuficiente"));
        }
    }

    @Test public void unknownSizeStillNeedsReserveAndRuntimeLimit() throws Exception {
        ApkImportPreflight.checkClaimedSize(-1, 256L * 1024 * 1024);
        ApkImportPreflight.checkProgress(16L * 1024 * 1024, 90L * 1024 * 1024);
        try {
            ApkImportPreflight.checkProgress(1024L * 1024 * 1024 + 1,
                4L * 1024 * 1024 * 1024);
            fail("Actual streamed content must be bounded");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("1 GiB"));
        }
    }

    @Test public void periodicDiskChecksAvoidPerChunkStatCalls() {
        assertFalse(ApkImportPreflight.shouldRecheck(30L * 1024 * 1024, 0));
        assertTrue(ApkImportPreflight.shouldRecheck(32L * 1024 * 1024, 0));
        assertFalse(ApkImportPreflight.shouldRecheck(40L * 1024 * 1024,
            32L * 1024 * 1024));
    }
}
