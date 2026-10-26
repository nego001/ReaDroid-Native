package com.readroid.app;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.IOException;

import static org.junit.Assert.*;

/** M2.7 protects full 128-bit equality, table growth, and the entry quota. */
@RunWith(AndroidJUnit4.class)
public final class ApkPrimitiveFingerprintInstrumentedTest {
    @Test public void growsWithoutLosingNamesOrMistakingSlotCollisionsForDuplicates()
            throws Exception {
        ApkPathFingerprintSet paths = new ApkPathFingerprintSet();
        assertEquals(256, paths.capacity());
        for (int i = 0; i < 20000; i++)
            paths.requireUnique("assets/pathed/subfolder/item_" + i + ".json");
        assertEquals(20000, paths.size());
        assertTrue(paths.capacity() >= 32768);
        assertTrue(paths.capacity() <= 65536);
        // Thousands of distinct hashes must have shared table buckets while
        // being admitted, so an ordinary slot collision is NOT a duplicate.
        paths.requireUnique("assets/pathed/subfolder/CAPS.json");
        paths.requireUnique("assets/pathed/subfolder/caps.json");
        assertEquals(20002, paths.size());
        try {
            paths.requireUnique("assets/pathed/subfolder/item_19999.json");
            fail("Duplicate from before table growth should still be rejected");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("duplicada"));
        }
        assertEquals(20002, paths.size());
    }

    @Test public void exactQuotaAllows150000ButRejectsNextWithoutAllocation()
            throws Exception {
        ApkPathFingerprintSet paths = new ApkPathFingerprintSet();
        for (int i = 0; i < 150000; i++)
            paths.requireUnique("p/" + i);
        assertEquals(150000, paths.size());
        assertEquals(262144, paths.capacity());
        try {
            paths.requireUnique("p/extra");
            fail("Entry 150001 must not be admitted");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("150 mil"));
        }
        assertEquals(150000, paths.size());
        assertEquals(262144, paths.capacity());
    }

    @Test public void emptyAndUnicodePathsHaveDeterministicEquality()
            throws Exception {
        ApkPathFingerprintSet paths = new ApkPathFingerprintSet();
        paths.requireUnique("");
        paths.requireUnique("á");
        paths.requireUnique("a\u0301");
        assertEquals(3, paths.size());
        try {
            paths.requireUnique("");
            fail("Empty fingerprint should still be recognised as duplicate");
        } catch (IOException expected) {
            assertTrue(expected.getMessage().contains("duplicada"));
        }
        try {
            paths.requireUnique(null);
            fail("Null path may not be accepted");
        } catch (IOException expected) {
            assertNotNull(expected.getMessage());
        }
        assertEquals(3, paths.size());
    }
}
