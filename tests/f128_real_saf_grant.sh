#!/usr/bin/env bash
# F1.28: REAL DocumentsUI permission acquisition, force-stop and revocation.
# Disposable Google Actions emulator only; never a connected physical device.
set -euo pipefail
PKG=com.readroid.app
RUNNER=com.readroid.app.test/androidx.test.runner.AndroidJUnitRunner
TEST=com.readroid.app.F128RealSafGrantInstrumentedTest
FIXTURE=/sdcard/Download/F128_saf_permission_probe.apk
DEBUG_APK=app/build/outputs/apk/debug/app-debug.apk
TEST_APK=app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk

cleanup() {
    adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
    adb shell rm -f "$FIXTURE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

[[ -f "$DEBUG_APK" && -f "$TEST_APK" ]]
adb install -r "$DEBUG_APK" >/dev/null
adb install -r "$TEST_APK" >/dev/null

# Use the actual compiled debug APK; never create a counterfeit APK fixture.
# The Downloads root is supplied by Android's real DocumentsProvider.
adb shell mkdir -p /sdcard/Download
adb push "$DEBUG_APK" "$FIXTURE" >/dev/null
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://$FIXTURE" >/dev/null

run_case() {
    local method=$1 output
    output=$(adb shell am instrument -w -e class "$TEST#$method" "$RUNNER" 2>&1 | tr -d '\r')
    printf '%s\n' "$output"
    if ! grep -qE '^OK \\(1 test\\)' <<<"$output" ||
       grep -qE 'FAILURES!!!|INSTRUMENTATION_FAILED' <<<"$output"; then
        echo "F128 FAIL: $method" >&2
        return 1
    fi
}
run_case f128ObtainPersistedGrantFromSystemPicker
adb shell am force-stop "$PKG"
run_case f128AfterColdStartRevokeRealPersistedGrant
adb shell am force-stop "$PKG"
run_case f128NextProcessRejectsRevokedGrant
echo "F128_REAL_SAF_GRANT_REVOKE_PASS"
