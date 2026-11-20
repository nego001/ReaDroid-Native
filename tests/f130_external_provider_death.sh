#!/usr/bin/env bash
# F1.30 real remote-provider force-stop outside AndroidJUnitRunner.
# Disposable Actions emulator + fixed debug-only Activity and fixture package.
set -euo pipefail

APP=com.readroid.app
FIXTURE=com.readroid.f130fixture
REMOTE_PROCESS=com.readroid.f130fixture:provider
HARNESS=com.readroid.app/.F130CrashHarnessActivity
RESULT=files/f130_crash_result
ROOT=cache

run_as() {
    adb shell "run-as $APP sh -c '$1'" | tr -d '\r'
}
pid_for() {
    adb shell pidof "$1" 2>/dev/null | tr -d '\r\n' || true
}
fail() { echo "F130 FAIL: $*" >&2; exit 1; }
install_ci_apk() {
    local apk="$1" attempt output=""
    for attempt in 1 2 3; do
        if output=$(adb install -r "$apk" 2>&1) &&
           [[ "$output" == *Success* ]]; then
            echo "F130 installed disposable APK: $apk"
            return 0
        fi
        echo "F130 install attempt $attempt failed: $output" >&2
        sleep 2
    done
    fail "unable to reinstall CI-only debug APK: $apk"
}

cleanup() {
    # Kill only the two disposable debug apps; do not clear data or user files.
    adb shell am force-stop "$FIXTURE" >/dev/null 2>&1 || true
    adb shell am force-stop "$APP" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'rc=$?; echo "F130 unexpected command failure line $LINENO exit=$rc" >&2' ERR

DEBUG_APK=app/build/outputs/apk/debug/app-debug.apk
[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == "1" ]] ||
    fail "physical devices are never authorized for process-kill tests"
[[ -f "$DEBUG_APK" ]] || fail "debug app build absent"
install_ci_apk "$DEBUG_APK"
adb shell pm path "$FIXTURE" | grep -q 'package:' ||
    fail "independent provider APK not installed"
run_as "test ! -e $RESULT" || fail "fixture result already existed"
for own in readroid_F130accepted123.apk readroid_F130accepted123.apk.idx.db recovery_f130.enc; do
    run_as "test ! -e $ROOT/$own" || fail "fixture already exists: $own"
done
preexisting=$(run_as "ls $ROOT/readroid_*.apk.pending 2>/dev/null | wc -l" |
    tr -d '[:space:]')
[[ "$preexisting" == 0 ]] || fail "unowned pending cache already exists"

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

# The provider must still have the client blocked before we kill it.
[[ "$(run_as "cat $RESULT")" == RUNNING ]] ||
    fail "import finished before provider termination"
adb shell am force-stop "$FIXTURE"
[[ -z "$(pid_for "$REMOTE_PROCESS" || true)" ]] ||
    fail "remote provider survived force-stop"

new_owner_pid=$(pid_for "$APP" || true)
if [[ "$new_owner_pid" != "$owner_pid" ]]; then
    # Android can kill an importer that holds a *stable* ContentProvider
    # reference when that provider dies. This is a real platform cascade,
    # not an in-process catchable IOException. Reopen the app, exercising
    # F1.26's ImportCrashJanitor on the FIRST Activity of a new process.
    adb shell am start -W -n "$APP/.MainActivity" >/dev/null
    new_owner_pid=$(pid_for "$APP")
    [[ -n "$new_owner_pid" && "$new_owner_pid" != "$owner_pid" ]] ||
        fail "consumer process did not restart after cascading provider death"
    verdict=PASS_CASCADE_COLD_START
else
    verdict=""
    for _ in $(seq 1 20); do
        verdict=$(run_as "cat $RESULT" 2>/dev/null || true)
        case "$verdict" in
            PASS_*) break ;;
            FAIL_*) fail "harness reported $verdict" ;;
        esac
        sleep 1
    done
    case "$verdict" in
        PASS_ZIP_REJECTED|PASS_TRANSPORT_REJECTED) ;;
        *) fail "importer never rejected killed provider: $verdict" ;;
    esac
fi

# Both modes must preserve the old data and leave NO transient candidate.
run_as "test -f $ROOT/readroid_F130accepted123.apk"
run_as "test -f $ROOT/readroid_F130accepted123.apk.idx.db"
run_as "test -f $ROOT/recovery_f130.enc"
[[ "$(run_as "cat $ROOT/readroid_F130accepted123.apk")" == "accepted before crash" ]]
[[ "$(run_as "cat $ROOT/readroid_F130accepted123.apk.idx.db")" == "saved index" ]]
[[ "$(run_as "cat $ROOT/recovery_f130.enc")" == "saved checkpoint" ]]
remaining=$(run_as "ls $ROOT/readroid_*.apk.pending 2>/dev/null | wc -l" |
    tr -d '[:space:]')
[[ "$remaining" == 0 ]] || fail "cold restart retained unfinished SAF candidate"
echo "F130_EXTERNAL_PROVIDER_DEATH_PASS provider_pid=$old_provider_pid old_owner=$owner_pid new_owner=$new_owner_pid verdict=$verdict"
