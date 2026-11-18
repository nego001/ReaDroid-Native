#!/usr/bin/env bash
# F1.30 real remote-provider force-stop outside AndroidJUnitRunner.
# Disposable Actions emulator + fixed debug-only Activity and fixture package.
set -euo pipefail

APP=com.readroid.app
FIXTURE=com.readroid.f130fixture
REMOTE_PROCESS=com.readroid.f130fixture:provider
HARNESS=com.readroid.app/.F130CrashHarnessActivity
RESULT=files/f130_crash_result
ROOT=cache/f130_crash_sandbox

run_as() {
    adb shell "run-as $APP sh -c '$1'" | tr -d '\r'
}
pid_for() {
    adb shell pidof "$1" 2>/dev/null | tr -d '\r\n'
}
fail() { echo "F130 FAIL: $*" >&2; exit 1; }
cleanup() {
    # Kill only the two disposable debug apps; do not clear data or user files.
    adb shell am force-stop "$FIXTURE" >/dev/null 2>&1 || true
    adb shell am force-stop "$APP" >/dev/null 2>&1 || true
}
trap cleanup EXIT

DEBUG_APK=app/build/outputs/apk/debug/app-debug.apk
[[ -f "$DEBUG_APK" ]] || fail "debug app build absent"
adb install -r "$DEBUG_APK" >/dev/null
adb shell pm path "$FIXTURE" | grep -q 'package:' ||
    fail "independent provider APK not installed"
run_as "test ! -e $RESULT" || fail "fixture result already existed"
run_as "test ! -e $ROOT" || fail "fixture cache already existed"

adb shell am force-stop "$APP"
adb shell am start -W -n "$HARNESS" >/dev/null
owner_pid=$(pid_for "$APP")
[[ -n "$owner_pid" ]] || fail "debug harness not running"

# Must observe real file bytes on disk while the external provider is alive.
# This proves the kill interrupts a live ContentResolver streaming import.
ready=0
for _ in $(seq 1 30); do
    old_provider_pid=$(pid_for "$REMOTE_PROCESS" || true)
    number=$(run_as "wc -c $ROOT/readroid_*.apk.pending" 2>/dev/null |
        awk 'NR==1 {print $1}' || true)
    if [[ -n "$old_provider_pid" && "${number:-0}" =~ ^[0-9]+$ ]] &&
       (( number > 0 )); then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]] || {
    run_as "cat $RESULT" || true
    fail "remote provider did not supply staged bytes"
}

adb shell am force-stop "$FIXTURE"
[[ -z "$(pid_for "$REMOTE_PROCESS" || true)" ]] ||
    fail "remote provider survived force-stop"
[[ "$(pid_for "$APP")" == "$owner_pid" ]] ||
    fail "importing app process died with external provider"

result=""
for _ in $(seq 1 20); do
    result=$(run_as "cat $RESULT" 2>/dev/null || true)
    case "$result" in
        PASS_*) break ;;
        FAIL_*) fail "harness reported $result" ;;
    esac
    sleep 1
done
case "$result" in
    PASS_ZIP_REJECTED|PASS_TRANSPORT_REJECTED) ;;
    *) fail "importer never rejected killed provider: $result" ;;
esac

run_as "test -f $ROOT/readroid_F130accepted123.apk"
run_as "test -f $ROOT/readroid_F130accepted123.apk.idx.db"
run_as "test -f $ROOT/recovery_f130.enc"
count=$(run_as "ls -1 $ROOT | wc -l" | tr -d '[:space:]')
[[ "$count" == 3 ]] || fail "unaccepted APK or partial cache survived"
echo "F130_EXTERNAL_PROVIDER_DEATH_PASS provider_pid=$old_provider_pid app_pid=$owner_pid verdict=$result"
