#!/usr/bin/env bash
# F1.35: real Android force-stop DURING an encrypted checkpoint verification.
# Only fixed debug fixtures on disposable emulator; never a physical phone.
set -euo pipefail
APP=com.readroid.app
ACTIVITY="$APP/.F135VerifierCrashHarnessActivity"
RUNNER="$APP.test/androidx.test.runner.AndroidJUnitRunner"
TEST=com.readroid.app.F135VerifierCrashInstrumentedTest
LAB=files/f135_ci_verify_lab
APK=app/build/outputs/apk/debug/app-debug.apk
TEST_APK=app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk

fail() { echo "F135 FAIL: $*" >&2; exit 1; }
install_ci_apk() {
    local apk="$1" attempt output=""
    for attempt in 1 2 3; do
        if output=$(adb install -r "$apk" 2>&1) &&
           [[ "$output" == *Success* ]]; then
            echo "F135 installed disposable APK: $apk"
            return 0
        fi
        echo "F135 install attempt $attempt failed: $output" >&2
        sleep 2
    done
    fail "unable to reinstall CI-only debug APK: $apk"
}

run_as() { adb shell "run-as $APP sh -c '$1'" | tr -d '\r'; }
pid() { adb shell pidof "$APP" 2>/dev/null | tr -d '\r\n' || true; }
status() { run_as "cat $LAB/status" 2>/dev/null || true; }
cleanup() { adb shell am force-stop "$APP" >/dev/null 2>&1 || true; }
trap cleanup EXIT
trap 'rc=$?; echo "F135 unexpected command failure line $LINENO exit=$rc" >&2' ERR

[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == "1" ]] ||
    fail "physical devices are not authorized"
[[ -f "$APK" && -f "$TEST_APK" ]] || fail "missing debug binaries"
install_ci_apk "$APK"
install_ci_apk "$TEST_APK"
run_as "test ! -e $LAB" || fail "F135 private test folder already exists"

start_phase() {
    local phase=$1 expected=$2 value=""
    adb shell am force-stop "$APP"
    adb shell am start -W -n "$ACTIVITY" --es phase "$phase" >/dev/null
    for _ in $(seq 1 30); do
        value=$(status)
        [[ "$value" == "$expected" ]] && return 0
        case "$value" in FAIL_*) fail "$phase marked $value" ;; esac
        sleep 1
    done
    fail "$phase did not reach $expected: $(status)"
}
run_test() {
    local method=$1 output
    output=$(adb shell am instrument -w -e class "$TEST#$method" "$RUNNER" 2>&1 | tr -d '\r')
    printf '%s\n' "$output"
    if ! grep -Fq 'OK (1 test)' <<<"$output" ||
       grep -qE 'FAILURES!!!|INSTRUMENTATION_FAILED' <<<"$output"; then
        fail "instrumentation $method failed"
    fi
}
force_stop_verifier() {
    local expectedStages=$1 old new number
    old=$(pid)
    [[ -n "$old" ]] || fail "verification app not running"
    number=$(run_as "ls $LAB/vault/checkpoint-*.tmp 2>/dev/null | wc -l" |
        tr -d '[:space:]')
    [[ "$number" == "$expectedStages" ]] ||
        fail "expected $expectedStages uncommitted encrypted stages, found $number"
    run_as "test -s $LAB/vault/edit-plan-checkpoint.v1" ||
        fail "last committed ciphertext disappeared"
    adb shell am force-stop "$APP"
    [[ -z "$(pid)" ]] || fail "verifier process survived force-stop"
    local launch
    launch=$(adb shell am start -W -n "$APP/.MainActivity" 2>&1) ||
        fail "could not start MainActivity after force-stop: $launch"
    new=""
    for _ in $(seq 1 12); do
        new=$(pid)
        if [[ -n "$new" && "$new" != "$old" ]]; then break; fi
        sleep 1
    done
    [[ -n "$new" && "$new" != "$old" ]] ||
        fail "verifier cold start never produced fresh PID (old=$old observed=$new launch=$launch)"
    echo "F135_REAL_VERIFIER_KILL old_pid=$old new_pid=$new"
}

start_phase seed SEEDED
start_phase verify_1 READING_1
force_stop_verifier 1
run_test f135FirstMidVerificationCrashPreservesA

start_phase verify_2 READING_2
force_stop_verifier 2
run_test f135SecondMidVerificationCrashPreservesA

start_phase commit_b COMMITTED_B
run_test f135CommittedBStillDecryptsAfterTwoCrashes
run_as "test ! -e $LAB" || fail "F135 test-only files not removed"
echo "F135_VERIFIER_PROCESS_DEATH_PASS"
