# PE-S2.18 | V3 signed before/after host supplement, still HOLD

## Scope and precise state

This phase introduces an **explicitly versioned v3 supplement** for the two **unsigned, reviewer-host sidecar** samples produced by PE-S2.17. It does not modify any S1.63 v1 or PE-S2.16 v2 manifest, signature, schema or filename. It does NOT provide independently authenticated physical host provenance, native Arch guest isolation, journald effective quota or a release approval.

The new script `tools/pe_arch_vm_s2_18_signed_host_pair.py` defines the separate canonical JSON `external-host-two-phase-supplement-v3.json`, signed only via OpenSSH Ed25519 under the new namespace `negresco-pe-s2-18-host-two-phase-supplement-v3`. The detached signature filename is `external-host-two-phase-supplement-v3.sig`. The strict v3 manifest binds exact full source SHA, external challenge, independent session nonce, domain/UUID, observer principal, *both* before and after SHA-256 values, the existing S1.63 v1 and PE-S2.16 v2 manifest and signature SHA-256 values, host+guest records and S2.15 single sidecar SHA-256. All attestation and release flags are false; a signed V1 or V2 manifest cannot be substituted for a V3 signature because the namespace differs.

## Correct chronological workflow on a separately controlled reviewer host

1. Reviewer chooses and separately keeps a fresh challenge and non-reused session identifier, exact commit and domain/UUID. Capture S1.70 host and S1.71 guest records. The host and guest outputs must be genuinely collected by the independent reviewer, not invented in the user's guest.
2. Before any sealed observer signature, perform the **optional S2.15** single domstats capture and S2.17 `--phase before --capture-from-independent-host`. Preserve these SHA-256 values outside the guest and keep the original private files mode 0600. Do not run arbitrary Windows PE.
3. Between the two samples, run only the expressly approved synthetic workload in the isolated, disposable native Arch VM, collecting genuine cgroup/seccomp, /work, journald and descendant evidence through the approved native reviewer protocol. S2.18 itself **does not run the workload**.
4. Capture S2.17 `--phase after --capture-from-independent-host --expected-before-sha256 ...`. Preserve the after hash independently; offline review must confirm same session/UUID, before-hash chain and increasing libvirt-reported CPU time, but rising CPU time by itself does **not** prove the intended guest process ran.
5. Finish the four S1.63 records, run S1.65 manifest preparation and independently sign and verify S1.63 v1. Then prepare, independently sign and verify the **single sidecar v2 supplement** per PE-S2.16.
6. Execute `python -B tools/pe_arch_vm_s2_18_signed_host_pair.py --observer-dir ... --custody-dir ...` with **all `--expected-...` pins**, including signed v1/v2 manifests+signatures, S2.15 sidecar and S2.17 before/after SHA-256 values. The V3 program verifies both prior **real detached signatures** and both raw host session samples, then atomically publishes a private unsigned V3 JSON without touching a signing key, refusing any overwrite.
7. The *observer*, outside the guest/operator boundary, signs the V3 manifest using `ssh-keygen -Y sign -f <observer-private-key> -n negresco-pe-s2-18-host-two-phase-supplement-v3 <manifest-path>`. Rename the produced `.json.sig` to `external-host-two-phase-supplement-v3.sig`, private 0600. Separately pin the manifest SHA256 and signature SHA256.
8. Call the V3 program with `--verify-existing --expected-extension-manifest-sha256 ... --expected-extension-signature-sha256 ...` and all original external pins. It verifies exact canonical bytes, namespace-specific real Ed25519 signature, pinned v1/v2 files, the two S2.17 samples and their monotonic counters, then repeats the upstream checks. **Even a valid result returns code 2, status `SIGNED_PE_S2_18_EXTENSION_V3_VERIFIED_RELEASE_HOLD`.** No release gate must interpret that as approval.

## Security limits and testing

This adds a cryptographic signature and custody pinning to *both* host-reported phase texts; the v1 four files remain signed only by v1, the S2.15 single sidecar only by v2, and the S2.17 pair only by v3. Signatures authenticate bytes against chosen keys, not the origin or truth of the host metrics. A malicious operator able to influence the reviewer still can fabricate a coherent series.

CI exercises the schema, file custody and real disposable **OpenSSH Ed25519** keys, but **mocks virsh**; Ubuntu real Ghidra/Bubblewrap/seccomp uses synthetic PE as data and mocked cgroups, and Arch userspace is only a container. No independently provisioned Arch VM attestation, authenticated host physical control, journald hard quota, cgroups+seccomp joint guest evidence or actual external session is demonstrated.

**Mandatory state:** PR #47 Draft, no merge, APK, OTA, or execution/analysis of an unknown Windows PE, release authorization false.
