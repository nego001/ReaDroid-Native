#!/usr/bin/env bash
# F1.32: kill checkpoint writer AFTER fsync BEFORE atomic replacement.
# Disposable emulator only, never user-owned files, production vault or phone.
set -euo pipefail

PKG=com.readroid.app
HARNESS="$PKG/.F132CheckpointHarnessActivity"
RUNNER="$PKG.test/androidx.test.runner.AndroidJUnitRunner"
TEST=com.readroid.app.F132CheckpointCrashInstrumentedTest
LAB=files/f132_ci_checkpoint_lab
DEBUG_APK=app/build/outputs/apk/debug/app-debug.apk
TEST_APK=app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk

fail() { echo "F132 FAIL: $*" >&2; exit 1; }
install_ci_apk() {
    local apk="$1" attempt output=""
    for attempt in 1 2 3; do
        if output=$(adb install -r "$apk" 2>&1) &&
           [[ "$output" == *Success* ]]; then
            echo "F132 installed disposable APK: $apk"
            return 0
        fi
        echo "F132 install attempt $attempt failed: $output" >&2
        sleep 2
    done
    fail "unable to reinstall CI-only debug APK: $apk"
}

run_as() { adb shell "run-as $PKG sh -c '$1'" | tr -d '\r'; }
pid() { adb shell pidof "$PKG" 2>/dev/null | tr -d '\r\n' || true; }
marker() { run_as "cat $LAB/status" 2>/dev/null || true; }
cleanup() { adb shell am force-stop "$PKG" >/dev/null 2>&1 || true; }
trap cleanup EXIT
trap 'rc=$?; echo "F132 unexpected command failure line $LINENO exit=$rc" >&2' ERR

[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == "1" ]] ||
    fail "CI emulator required; refuse physical device"
[[ -f "$DEBUG_APK" && -f "$TEST_APK" ]] || fail "missing debug builds"
install_ci_apk "$DEBUG_APK"
install_ci_apk "$TEST_APK"
run_as "test ! -e $LAB" || fail "F132 sandbox already exists"

start_phase() {
    local phase=$1 expected=$2 state
    adb shell am force-stop "$PKG"
    adb shell am start -W -n "$HARNESS" --es phase "$phase" >/dev/null
    for i in $(seq 1 30); do
        state=$(marker)
        if [[ "$state" == "$expected" ]]; then return 0; fi
        case "$state" in FAIL_*) fail "$phase reported $state" ;; esac
        sleep 1
    done
    fail "$phase did not reach $expected (observed $(marker))"
}
run_test() {
    local method=$1 output
    output=$(adb shell am instrument -w -e class "$TEST#$method" "$RUNNER" 2>&1 | tr -d '\r')
    printf '%s\n' "$output"
    if ! grep -Fq "OK (1 test)" <<<"$output" ||
       grep -qE 'FAILURES!!!|INSTRUMENTATION_FAILED' <<<"$output"; then
        fail "$method instrumentation failed"
    fi
}
verify_staged() {
    local expected=$1 count
    count=$(run_as "ls $LAB/vault/checkpoint-*.tmp 2>/dev/null | wc -l" |
        tr -d '[:space:]')
    [[ "$count" == "$expected" ]] ||
        fail "expected $expected synced encrypted stages; found $count"
    run_as "test -s $LAB/vault/edit-plan-checkpoint.v1" ||
        fail "last committed checkpoint disappeared"
}
kill_staged_writer() {
    local expected=$1 old_pid new_pid
    old_pid=$(pid)
    [[ -n "$old_pid" ]] || fail "app process already dead before kill"
    verify_staged "$expected"
    adb shell am force-stop "$PKG"
    [[ -z "$(pid)" ]] || fail "process survived external force-stop"
    local launch
    launch=$(adb shell am start -W -n "$PKG/.MainActivity" 2>&1) ||
        fail "could not start MainActivity after force-stop: $launch"
    new_pid=""
    for _ in $(seq 1 12); do
        new_pid=$(pid)
        if [[ -n "$new_pid" && "$new_pid" != "$old_pid" ]]; then break; fi
        sleep 1
    done
    [[ -n "$new_pid" && "$new_pid" != "$old_pid" ]] ||
        fail "cold start never produced a distinct PID (old=$old_pid observed=$new_pid launch=$launch)"
    echo "F132_COLD_RESTART old_pid=$old_pid new_pid=$new_pid"
}

start_phase seed SEEDED_A
run_as "test -s $LAB/vault/edit-plan-checkpoint.v1" ||
    fail "original encrypted checkpoint absent"
start_phase stage_b STAGED_B
kill_staged_writer 1
run_test f132FirstCrashPreservesCommittedA
start_phase commit_b COMMITTED_B
run_test f132SuccessfulAtomicReplacementAcceptsB
start_phase stage_c STAGED_C
kill_staged_writer 2
run_test f132SecondCrashPreservesCommittedB
run_as "test ! -e $LAB" || fail "test-only checkpoint cleanup incomplete"
echo "F132_CHECKPOINT_ATOMIC_CRASH_PASS"
