# PE-S2.17 | Host libvirt before/after session pair: no VM attestation

## Status
Implementation and simulated CI contracts. The external reviewer has NOT submitted a real independent native Arch VM observation. PR #47 must stay Draft: no merge, APK, OTA, or execution of unknown Windows PE.

## The actual improvement

`tools/pe_arch_vm_s2_17_host_two_phase.py` provides a **two-phase, explicitly opted-in, bounded read-only libvirt collection on the REVIEWER'S host**, never in the guest. The exact source commit, independently selected 64-character reviewer challenge and *distinct* session ID, domain name/UUID and pinned S1.70 host and S1.71 guest record SHA-256 are required at both phases.

1. With independent reviewer-controlled `virsh` on `qemu:///system` and prior host/guest records captured, use `--phase before --capture-from-independent-host` **before synthetic Ghidra work**. The program reads UUID/state before and after `domstats --raw --state --cpu-total`, with fixed argv, read-only connection and bounded time/output. It publishes **one** immutable private mode-0600 `reviewer-host-domstats-before.txt`, returning its SHA-256. The default command, without explicit capture flag, only validates inputs and returns NOT STARTED.
2. The reviewer records that SHA **outside the operator's control** and explicitly requests the existing, synthetic-only approved analysis in the disposable VM. This script DOES NOT initiate guest work.
3. With the *same* pinned commit, challenge, session, domain/UUID and first record digest, use `--phase after --capture-from-independent-host --expected-before-sha256 <out-of-band SHA>` after the test. Its sole live host queries are the same readonly `virsh` calls. The after sample must report the same running domain UUID and a strictly increasing `cpu.time`. The first record is revalidated before and after the queries. A second no-overwrite file `reviewer-host-domstats-after.txt` is produced.
4. An offline reviewer with **both separately pinned SHA-256** values uses `--review-existing --expected-before-sha256 ... --expected-after-sha256 ...`. The strict canonical JSON schema, duplicate keys, nonfinite numbers, raw counters, session/UUID hashes and monotonic CPU counter are checked twice. A valid review returns **code 2 and HOLD**; code 0 is used for *capture only*. Both records are deliberately **NOT contained in S1.63 v1 or S2.16 v2 signature manifests** and are not authenticated host snapshots.

The tool does not mount filesystems or start/stop libvirt domains. It does not query the guest agent, run Ghidra, or execute PE samples. It refuses a pre-existing signed S1.63 package during new collection, refuses overwritten/symlinked records, and keeps all attestation/release flags false. It does not assume a trusted wall clock: timestamps are labeled untrusted.

## Critical limits

Two increasing libvirt CPU counters **are not proof that the intended workload ran between them**. The VM could have spent cycles on unrelated tasks, and a malicious operator could fabricate the text or substitute the host. The UUID is as reported by libvirt, not cryptographically attested hardware provenance. This *local continuity and reviewer challenge* still lacks independent trusted host custody, authenticated native Arch cgroup v2 + seccomp runtime, journald effective quota and descendant cleanup.

PE-S2.17's pair is an unsigned supplemental proof until a future explicitly versioned, separately signed extension includes both SHAs. The already existing S1.63 v1 and S2.16 v2 signatures remain intact. No standalone positive test result can override the release HOLD.
