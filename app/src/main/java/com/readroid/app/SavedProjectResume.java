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
        return decide(accepted, interrupted, hasRetainedWorkspace, false, checker);
    }

    /**
     * sameProcessRecreation is backed by a process-local random marker in
     * saved instance state. The marker cannot survive a killed process.
     */
    static Decision decide(Uri accepted, Uri interrupted, boolean hasRetainedWorkspace,
            boolean sameProcessRecreation, ReadGrant checker) {
        if (hasRetainedWorkspace) {
            // Retain the previous project, and retry a pending import only
            // if this is the same process or its URI grant is still persisted.
            Uri retry = validContentUri(interrupted) && (sameProcessRecreation
                    || permitted(interrupted, checker)) ? interrupted : null;
            return new Decision(accepted, retry, interrupted != null && retry == null);
        }
        // Configuration recreation: the Android document picker may have
        // supplied only a transient grant. Preserve the already-started action
        // within this still-alive process, with normal SAF reads still required.
        if (sameProcessRecreation) {
            if (validContentUri(interrupted))
                return new Decision(accepted, interrupted, false);
            if (validContentUri(accepted))
                return new Decision(accepted, accepted, false);
        }
        // Process death: never promote an unaccepted pending import. An
        // accepted URI may be reimported only with a persisted read grant.
        if (permitted(accepted, checker))
            return new Decision(accepted, accepted, false);
        return new Decision(null, null, accepted != null || interrupted != null);
    }

    private static boolean validContentUri(Uri uri) {
        return uri != null && "content".equals(uri.getScheme());
    }
}
