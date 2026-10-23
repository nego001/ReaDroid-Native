#!/usr/bin/env bash
# Record a real, populated Explorer screen with a synthetic test-only ZIP.
# Run AFTER Gradle instrumentation; Gradle may uninstall the debug application.
set -euo pipefail

api="${1:-}"
case "$api" in
  29|35) ;;
  *) echo "P7_CAPTURE_FAIL: expected Android API 29 or 35" >&2; exit 2 ;;
esac

test -s app/build/outputs/apk/debug/app-debug.apk || {
  echo "P7_CAPTURE_FAIL: missing debug target" >&2
  exit 3
}
mapfile -t test_apks < <(find app/build/outputs/apk/androidTest -type f -name '*androidTest.apk' -print)
if (( ${#test_apks[@]} != 1 )) || [[ ! -s "${test_apks[0]:-}" ]]; then
  echo "P7_CAPTURE_FAIL: expected exactly one debug instrumentation APK" >&2
  exit 4
fi

adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r "${test_apks[0]}"

capture_output="$(adb shell am instrument -w -r \
  -e class com.readroid.app.P7ExplorerPopulatedCaptureInstrumentedTest \
  com.readroid.app.test/androidx.test.runner.AndroidJUnitRunner)"
printf '%s\n' "$capture_output"
if ! grep -Fq 'OK (1 test)' <<< "$capture_output"; then
  echo "P7_CAPTURE_FAIL: isolated Android test was not successful" >&2
  exit 5
fi

target="p7-explorer-populated-android-${api}.png"
# The app is still installed; read its own screenshot before other smokes.
adb exec-out run-as com.readroid.app cat files/p7-explorer-populated.png > "$target"
python3 - "$target" <<'PY'
from pathlib import Path
import sys
from tools.p7_capture_manifest import inspect_png
dimensions, digest, size = inspect_png(Path(sys.argv[1]))
print(f"P7_POPULATED_PNG_OK dimensions={dimensions} bytes={size} sha256={digest}")
PY
