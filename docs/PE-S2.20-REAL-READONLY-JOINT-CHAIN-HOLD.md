# PE-S2.20 | REAL readonly offline V1/V2/V3 + guest receipt, host and VM **still HOLD**

## Scope

This phase closes a **test coverage gap** in PE-S2.19. The 14 existing tests verified real temporary Ed25519 signatures but mocked the local native receipt verifier and Git commit validator. PE-S2.20 adds a **real, unprivileged Bubblewrap mount test** which verifies the full chain (V1/V2/V3 detached OpenSSH signatures, locally generated receipt, its original source hashes, actual clean Git HEAD and readonly mount flags) **without monkeypatching any of the inner verifiers**.

It is a CI safety integration, **not a host/guest attestation**. In the outer test setup, the libvirt host samples are synthetic and manually mocked, and the native acceptance report is a synthetic fixture, not the output of Ghidra or an independent Arch guest. This is explicit in the test's JSON outputs. It NEVER executes an unknown Windows PE or invokes guest workloads.

## Execution in ordinary Ubuntu CI

The new `tests/pe_s2_20_real_mount_joint_review_ci.py`:
1. Starts with a scratch directory owned by the unprivileged CI user, copies only the versioned `SOURCE_FILES` manifest, makes a **real fresh Git commit**, and writes a local native receipt with a full self-reported synthetic native acceptance report and genuine SHA-256 of that scratch checkout.
2. Constructs the S1.70/S1.71, S2.13 host logs, S2.15 single `domstats` sample and S2.17 before/after pair with **explicitly mocked virsh counters**. Every record uses the scratch Git HEAD, same reviewer challenge/session, domain UUID and the actual synthetic native receipt digest.
3. Signs the S1.63 V1, S2.16 V2, S2.18 V3 manifests with **fresh disposable OpenSSH Ed25519 private keys**, keeping the keys outside any sandbox mount. Stores only the *public* allowed signers in the observer/custody evidence.
4. Starts Bubblewrap (actual `--unshare-all` user/network namespaces), binds the *source checkout* as readonly, binds the public-only signed records and the native receipt as readonly, and makes the reviewer code itself readonly. The subprocess calls PE-S2.19's **real** `verify_reviewer_session`, which in turn runs the real Git, real `verify_local_receipt` and V1/V2/V3 OpenSSH signature verifiers without mock instrumentation, including kernel `fstatvfs` readonly checks. No private signing key enters the container.
5. Repeats four modes with exact expected outcomes:
   - Valid readonly source and matching fully signed package: `PASS_PE_S2_20_REAL_READONLY_JOINT_HANDOFF_HOLD` (the linked validator still returns a **HOLD**, not release).
   - Real writable source bind: rejected.
   - Real readonly *tampered* source files: rejected.
   - Wrong externally provided V3 detached signature digest: rejected.
6. Checks the schema, status and refusal flags for every mode in GitHub Actions. No arbitrary exit or Python crash counts as a successful negative test.

The runner reuses the already pinned real Bubblewrap/Ghidra installation from the existing workflow, **but Ghidra is not invoked by this phase**, and not a real native Arch acceptance.

## Unresolved human-operated review

The reviewer still must independently provision and manage a disposable native Arch VM and separate QEMU/libvirt host, choose the commit and challenge **before** the test, collect real runtime cgroup v2 + seccomp, bounded /work ENOSPC, journald effective hard quota, process descendants and cleanup, and preserve authentically timestamped host and guest evidence. The real signed V1/V2/V3 package must then be correlated with the *actual* native guest receipt under readonly source and independently pinned bytes, by PE-S2.19.

A green CI for this phase means **only that the offline chain behaves correctly on the runner with synthetic VM data**, not that a real VM was verified. Release/merge and any APK/OTA remain **HOLD**; PR #47 remains Draft. The next necessary action is an external reviewer-operated run, not an additional signature version.
