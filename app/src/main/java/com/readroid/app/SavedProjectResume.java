package com.readroid.app;

import android.net.Uri;

/**
 * F1.19: distinguish Activity recreation from process-death restoration.
 *
 * A nonconfiguration workspace is already owned by the current Activity
 * generation. Without one, a saved URI is only a suggestion: auto-reimport
 * is allowed solely for a previously ACCEPTED document with an Android-
 * persisted read grant. An interrupted/unaccepted import is NEVER replayed
 * after process death. All actual reads remain subject to provider checks.
 */
final class SavedProjectResume {
    interface ReadGrant {
        boolean hasPersistedRead(Uri uri);
    }

    static final class Decision {
        final Uri acceptedReference;
        final Uri reimport;
        final boolean requiresReselection;

        Decision(Uri acceptedReference, Uri reimport, boolean requiresReselection) {
            this.acceptedReference = acceptedReference;
            this.reimport = reimport;
            this.requiresReselection = requiresReselection;
        }
    }

    private SavedProjectResume() {}

    static boolean permitted(Uri uri, ReadGrant checker) {
        if (uri == null || checker == null
                || !"content".equals(uri.getScheme()))
            return false;
        try {
            return checker.hasPersistedRead(uri);
        } catch (SecurityException | IllegalArgumentException unavailable) {
            return false;
        }
    }

    static Decision decide(Uri accepted, Uri interrupted, boolean hasRetainedWorkspace,
            ReadGrant checker) {
        if (hasRetainedWorkspace) {
            // Keep the verified in-memory project; denied/missing permissions
            // must not replace it or discard its unsaved EditPlan.
            Uri retry = permitted(interrupted, checker) ? interrupted : null;
            return new Decision(accepted, retry,
                interrupted != null && retry == null);
        }
        // Process death: no trusted retained workspace. An interrupted picker
        // never establishes user acceptance even with a persisted URI grant.
        if (permitted(accepted, checker))
            return new Decision(accepted, accepted, false);
        return new Decision(null, null, accepted != null || interrupted != null);
    }
}
