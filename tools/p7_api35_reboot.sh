#!/usr/bin/env bash
# The emulator runner runs workflow script lines in separate shell processes.
# Keep conditional API35 reboot entirely in this ONE invoked Bash script.
set -euo pipefail
api="${1:?Android API level required}"
case "$api" in
  29) echo "P7_API29_NO_REBOOT before compact viewport smoke"; exit 0 ;;
  35) ;;
  *) echo "Unsupported API for guarded reboot: $api" >&2; exit 2 ;;
esac

adb reboot
timeout 150s adb wait-for-device
booted=""
for attempt in $(seq 1 60); do
  booted="$(timeout 8s adb shell getprop sys.boot_completed | tr -d '\r')" || booted=""
  if [ "$booted" = "1" ]; then break; fi
  sleep 2
done
if [ "$booted" != "1" ]; then
  echo "API35 did not finish boot after the guarded reboot" >&2
  exit 1
fi
adb shell pm path com.readroid.app | grep -Fq 'package:'
adb shell wm size | grep -Fq 'Physical size:'
adb shell wm density | grep -Fq 'Physical density:'
echo "P7_API35_REBOOT_VERIFIED before compact viewport smoke"
