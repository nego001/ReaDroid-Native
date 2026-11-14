# PE-S2.19 | Signed host V3 + local guest native receipt: offline HOLD

## Goal / precise state

The approved CI from PE-S2.18 cryptographically checked the four-record S1.63 V1 manifest, S2.15 V2 sidecar, and S2.17 V3 before/after libvirt observations, but a separate missing gate remained: **the actual local guest native acceptance receipt must match the receipt SHA-256 in the signed V1 custody chain, and the same reviewer challenge/commit**.

`tools/pe_arch_vm_s2_19_reviewer_session_handoff.py` is a **read-only offline consistency validator** for an independent reviewer's already collected package, *not* a launcher. It never calls libvirt, Ghidra, shell, QEMU, network or VM tools, does not sign files, and does not execute any PE. It does not modify the V1/V2/V3 schemas or any existing receipt.

## Mandatory inputs

`--observer-dir`: private 0700 reviewer-owned directory with the actual V1/V2/V3 signed manifests, detached Ed25519 signatures, readonly libvirt records and pair files.

`--custody-dir`: separate private 0700 operator/reviewer custody folder with the actual local native receipt file, given as `--native-receipt`. The receipt filename may vary but must be a direct child of custody. The local receipt is **unsigned** and its SHA must be known independently. Do not use a copy edited to match the host record.

`--source-root`: separate, exact **read-only mounted Git checkout** at the reviewer-selected full commit; the receipt validator refuses a writable mount and verifies all manifest sources in two passes. The local Git HEAD, tracked source files and clean worktree must also pass, not merely the hashes embedded inside the self-reported receipt.

`--expected-native-receipt-sha256`: SHA-256 held by the reviewer outside the guest. This **must exactly equal `--expected-receipt-sha256` already fixed in the signed V1/V2/V3 custody chain**. Also pass `--expected-v3-manifest-sha256` and `--expected-v3-signature-sha256`, and every `--expected-...` value already required by PE-S2.18. None of these may be copied blindly from an untrusted operator report; the reviewer must pin them independently.

## Verifier sequence and output

1. Reject bad hashes/pins and receipt path before any receipt processing.
2. Read the actual native receipt with nofollow, private file metadata/size checks; require exact SHA-256 match to the signed external receipt pin.
3. Verify V3 detached signature and signed V2/V1 chain, S2.15 stats, S2.17 prior/final host samples and their before-hash chain.
4. Revalidate local unsigned native receipt's schema, full native acceptance report, challenge, all source-file hashes through a **read-only source view**, and explicit no-Windows-PE execution.
5. Recheck the local checkout's full Git commit, clean worktree, and tracked source list.
6. Re-read the receipt and re-verify V3 to reject persistent changes during review.
7. If all conditions pass, return `LOCAL_PE_S2_19_SIGNED_HOST_PAIR_AND_NATIVE_RECEIPT_CORRELATED_HOLD` with **all attestation, release and APK/OTA flags false**. Valid review and rejection **both exit code 2**; examine status fields, not a successful shell exit code.

## What it does NOT demonstrate

This can detect mixed signatures, stale or mismatched local native receipt, falsified claimed challenge/commit, absent read-only source view and changed files. It **does not prove any source timing or genuine physical host/VM provenance**, nor does the stored CPU counter establish that Ghidra ran in between. The local guest receipt is not signed by the hypervisor, and a signed statement of a self-report is not a hardware attestation. There is no actual attached independent native Arch VM in this environment. The required independent review of joint cgroup+seccomp, journald quotas, descendant shutdown, and direct host control is still **HOLD**.

CI tests the V1/V2/V3 **real disposable Ed25519 signatures** against synthetic host records and an intentionally mocked local receipt/checkout validator. No real native acceptance is asserted by these tests. Do not run unknown Windows executables or merge PR #47; no APK/OTA release.
