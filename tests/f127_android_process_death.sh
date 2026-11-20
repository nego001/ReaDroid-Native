#!/usr/bin/env bash
# F1.27: real, external Android process termination and cold-start cache safety.
# Runs only on the disposable GitHub Actions emulator, never on user devices.
set -euo pipefail

PKG=com.readroid.app
COMPONENT=com.readroid.app/.MainActivity
PARTIAL=readroid_F127partial123.apk.pending
ACCEPTED=readroid_F127accepted123.apk
INDEX=readroid_F127accepted123.apk.idx.db
RECOVERY=f127_recovery.enc
UNRELATED=readroid_unsigned_F127123.apk.pending
FIXTURES_CREATED=0

run_as() {
    # Fixed CI-only names/commands. All paths live in the debug app's cache.
    adb shell "run-as $PKG sh -c '$1'" | tr -d '\r'
}
get_pid() {
    adb shell pidof "$PKG" 2>/dev/null | tr -d '\r\n'
}
wait_for_pid() {
    local pid
    for _ in $(seq 1 15); do
        pid=$(get_pid || true)
        if [[ -n "$pid" ]]; then
            printf '%s' "$pid"
            return 0
        fi
        sleep 1
    done
    echo "F127 FAIL: app did not start (pidof empty)" >&2
    adb shell pm path "$PKG" || true
    adb shell dumpsys activity activities | grep -E 'readroid|mResumed' | tail -25 || true
    adb logcat -d -t 250 -v brief | grep -E 'FATAL EXCEPTION|com.readroid.app|ReaDroidImportCrash' | tail -35 || true
    return 1
}
cleanup() {
    # Only remove our fixtures when the preflight proved they were absent.
    # Never touch any existing data if a fixture name was already occupied.
    if [[ "$FIXTURES_CREATED" == 1 ]]; then
        run_as "rm -f cache/$PARTIAL cache/$ACCEPTED cache/$INDEX cache/$RECOVERY cache/$UNRELATED" >/dev/null 2>&1 || true
    fi
    adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Gradle's connectedAndroidTest may remove its installed APK on teardown.
# Re-install the debug build only inside this disposable CI emulator; do NOT
# assemble/upload a QA release or touch the user's physical device.
DEBUG_APK=app/build/outputs/apk/debug/app-debug.apk
if [[ ! -f "$DEBUG_APK" ]]; then
    echo "F127 FAIL: Gradle debug APK absent" >&2
    exit 1
fi
adb install -r "$DEBUG_APK"
adb shell pm path "$PKG"

# No synthetic Activity lifecycle callbacks: kill an actual running app PID.
adb shell am force-stop "$PKG"
adb shell am start -W -n "$COMPONENT"
pid_before=$(wait_for_pid)
run_as "mkdir -p cache"

# Refuse to overwrite fixtures from a previous run (or any existing data).
for file in "$PARTIAL" "$ACCEPTED" "$INDEX" "$RECOVERY" "$UNRELATED"; do
    run_as "test ! -e cache/$file"
done
FIXTURES_CREATED=1

# Stage a recognizable partially copied SAF filename in the app's private
# sandbox while that real app process is alive. Completed files must survive.
run_as "printf partial-f127 > cache/$PARTIAL"
run_as "printf accepted-f127 > cache/$ACCEPTED"
run_as "printf index-f127 > cache/$INDEX"
run_as "printf recovery-f127 > cache/$RECOVERY"
run_as "printf unrelated-f127 > cache/$UNRELATED"
run_as "test -f cache/$PARTIAL"

adb shell am force-stop "$PKG"
if [[ -n "$(get_pid || true)" ]]; then
    echo "F127 FAIL: old process still running after force-stop" >&2
    exit 1
fi
run_as "test -f cache/$PARTIAL"  # force-stop skips onDestroy and does not clean it

adb shell am start -W -n "$COMPONENT"
pid_after=$(wait_for_pid)
if [[ "$pid_before" == "$pid_after" ]]; then
    echo "F127 FAIL: fresh process has same PID" >&2
    exit 1
fi

# The first onCreate() in a NEW PROCESS must sweep only known partial copies.
run_as "test ! -e cache/$PARTIAL"
run_as "test -f cache/$ACCEPTED"
run_as "test -f cache/$INDEX"
run_as "test -f cache/$RECOVERY"
run_as "test -f cache/$UNRELATED"
[[ "$(run_as "cat cache/$ACCEPTED")" == "accepted-f127" ]]
[[ "$(run_as "cat cache/$INDEX")" == "index-f127" ]]
[[ "$(run_as "cat cache/$RECOVERY")" == "recovery-f127" ]]
[[ "$(run_as "cat cache/$UNRELATED")" == "unrelated-f127" ]]

echo "F127_PROCESS_DEATH_PASS old_pid=$pid_before new_pid=$pid_after"
