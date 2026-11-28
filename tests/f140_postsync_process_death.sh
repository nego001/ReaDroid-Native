#!/usr/bin/env bash
# F1.39: real emulator-only process death AFTER atomic rename AND directory fsync.
# This tests process termination; it does NOT emulate a power outage.
set -euo pipefail

APP=com.readroid.app
HARNESS="$APP/.F140PostSyncCrashHarnessActivity"
RUNNER="$APP.test/androidx.test.runner.AndroidJUnitRunner"
TEST=com.readroid.app.F140PostSyncCrashInstrumentedTest
LAB=files/f140_ci_postsync_lab
APK=app/build/outputs/apk/debug/app-debug.apk
TEST_APK=app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk

fail() { echo "F140 FAIL: $*" >&2; exit 1; }
install_ci_apk() {
    local apk="$1" attempt output=""
    for attempt in 1 2 3; do
        if output=$(adb install -r "$apk" 2>&1) &&
           [[ "$output" == *Success* ]]; then
            echo "F140 installed disposable APK: $apk"
            return 0
        fi
        echo "F140 install attempt $attempt failed: $output" >&2
        sleep 2
    done
    fail "unable to install F140 debug APK: $apk"
}
run_as() { adb shell "run-as $APP sh -c '$1'" | tr -d '\r'; }
pid() { adb shell pidof "$APP" 2>/dev/null | tr -d '\r\n' || true; }
status() { run_as "cat $LAB/status" 2>/dev/null || true; }
cleanup() { adb shell am force-stop "$APP" >/dev/null 2>&1 || true; }
trap cleanup EXIT
trap 'rc=$?; echo "F140 unexpected command failure line $LINENO exit=$rc" >&2' ERR

[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == "1" ]] ||
    fail "physical Android devices are not authorized"
[[ -f "$APK" && -f "$TEST_APK" ]] ||
    fail "debug binaries missing from emulator job"
install_ci_apk "$APK"
install_ci_apk "$TEST_APK"
run_as "test ! -e $LAB" || fail "F140 sandbox already exists"

start_phase() {
    local phase=$1 expected=$2 state=""
    adb shell am force-stop "$APP"
    adb shell am start -W -n "$HARNESS" --es phase "$phase" >/dev/null
    for _ in $(seq 1 30); do
        state=$(status)
        [[ "$state" == "$expected" ]] && return 0
        case "$state" in FAIL_*) fail "$phase reported $state" ;; esac
        sleep 1
    done
    fail "$phase never reached $expected (observed $(status))"
}
test_method() {
    local method=$1 output
    output=$(adb shell am instrument -w -e class "$TEST#$method" "$RUNNER" 2>&1 | tr -d '\r')
    printf '%s\n' "$output"
    if ! grep -Fq "OK (1 test)" <<<"$output" ||
       grep -qE 'FAILURES!!!|INSTRUMENTATION_FAILED' <<<"$output"; then
        fail "F140 $method instrumentation failed"
    fi
}
kill_after_move() {
    local lastSHA oldPID newPID numStages
    oldPID=$(pid)
    [[ -n "$oldPID" ]] || fail "writer process already absent before kill"
    run_as "test -s $LAB/vault/edit-plan-checkpoint.v1" ||
        fail "promoted checkpoint missing"
    run_as "test -s $LAB/promoted.sha256" ||
        fail "promoted SHA not materialized"
    numStages=$(run_as "ls $LAB/vault/checkpoint-*.tmp 2>/dev/null | wc -l" |
        tr -d '[:space:]')
    [[ "$numStages" == 0 ]] ||
        fail "atomic promotion left $numStages pending stages"
    adb shell am force-stop "$APP"
    [[ -z "$(pid)" ]] || fail "app survived real external force-stop"
    local launch
    launch=$(adb shell am start -W -n "$APP/.MainActivity" 2>&1) ||
        fail "could not start MainActivity after force-stop: $launch"
    newPID=""
    for _ in $(seq 1 12); do
        newPID=$(pid)
        if [[ -n "$newPID" && "$newPID" != "$oldPID" ]]; then break; fi
        sleep 1
    done
    [[ -n "$newPID" && "$newPID" != "$oldPID" ]] ||
        fail "post-sync cold start never produced fresh PID (old=$oldPID observed=$newPID launch=$launch)"
    echo "F140_POSTSYNC_COLD_START old_pid=$oldPID new_pid=$newPID"
}

start_phase seed SEEDED_A
run_as "test -s $LAB/accepted.sha256" ||
    fail "initial committed checkpoint hash absent"
start_phase promote_b PROMOTED_B_POST_SYNC
kill_after_move
test_method f140FirstPostSyncKillRecoversPromotedB
start_phase promote_c PROMOTED_C_POST_SYNC
kill_after_move
test_method f140SecondPostSyncKillRecoversPromotedC
start_phase commit_d COMMITTED_D
test_method f140CleanCommitAfterTwoCrashesRecoversD
run_as "test ! -e $LAB" ||
    fail "isolated F140 fixture cleanup incomplete"
echo "F140_POSTSYNC_PROCESS_DEATH_PASS"
