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
run_as() { adb shell "run-as $PKG sh -c '$1'" | tr -d '\r'; }
pid() { adb shell pidof "$PKG" 2>/dev/null | tr -d '\r\n'; }
marker() { run_as "cat $LAB/status" 2>/dev/null || true; }
cleanup() { adb shell am force-stop "$PKG" >/dev/null 2>&1 || true; }
trap cleanup EXIT

[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == "1" ]] ||
    fail "CI emulator required; refuse physical device"
[[ -f "$DEBUG_APK" && -f "$TEST_APK" ]] || fail "missing debug builds"
adb install -r "$DEBUG_APK" >/dev/null
adb install -r "$TEST_APK" >/dev/null
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
    adb shell am start -W -n "$PKG/.MainActivity" >/dev/null
    new_pid=$(pid)
    [[ -n "$new_pid" && "$new_pid" != "$old_pid" ]] ||
        fail "cold restart must have different PID"
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
