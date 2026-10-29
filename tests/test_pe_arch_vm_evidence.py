"""PE-S1.12: native Arch VM evidence receipt, not a signed attestation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_evidence as evidence
import pe_arch_vm_receipt_verify as review
from pe_ghidra_integrity import GHIDRA_RELEASE_SHA256


class PrivateNativeArchReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir(mode=0o700)
        self.source = self.root / "tools" / "synthetic.py"
        self.source.write_text("print('harmless fixture')\n", encoding="utf-8")
        self.private = self.root / "private-proof"
        self.private.mkdir(mode=0o700)
        self.dest = self.private / "acceptance.json"
        self.challenge = "0123456789abcdef" * 4
        source = mock.patch.object(evidence, "SOURCE_FILES",
                                   ("tools/synthetic.py",))
        source.start()
        self.addCleanup(source.stop)
        self.report = {
            "status": "PASS_PE_S1_5_ARCH_VM",
            "environment": {
                "status": "ARCH_VM_PREFLIGHT_PASSED",
                "vm_confirmed": True, "container": False,
                "root": False, "systemd_user_bus": True,
                "real_cgroup_test_executed": False},
            "descendants_terminated": True,
            "cgroup": {"memory_max": 4294967296, "pids_max": 128,
                       "cpu_quota": 200000, "cpu_period": 100000},
            "cgroup_lifecycle": {
                "status": "PASS_NATIVE_ARCH_CGROUP",
                "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
                "memory_max": 4294967296, "pids_max": 128,
                "cpu_quota": 200000, "cpu_period": 100000,
                "quota_private_proof": {
                    "verification": "guard_verified_before_bwrap",
                    "memory_max_bytes": 4294967296, "tasks_max": 128,
                    "cpu_quota": 200000, "cpu_period": 100000},
                "scope_cleanup_evidence": {
                    "scope": "negresco-pe-cccccccccccccccccccccccc.scope",
                    "verified": True, "scope_quiescent": True,
                    "stop_request_accepted": False, "load_state": "not-found",
                    "scope_collected": True, "cgroup_unpopulated": True,
                    "active_state": "inactive", "sub_state": "dead"},
                "ghidra_executed": False, "windows_binary_executed": False,
            },
            "descendant_lifecycle": {
                "status": "PASS_NATIVE_ARCH_DESCENDANTS",
                "scope": "negresco-pe-0123456789abcdef01234567.scope",
                "detached_sigterm_ignoring_child_terminated": True,
                "systemd_stop_succeeded": True,
                "quota_verified": True,
                "quota_private_proof": {
                    "verification": "guard_verified_before_bwrap",
                    "memory_max_bytes": 4294967296,
                    "tasks_max": 128,
                    "cpu_quota": 200000, "cpu_period": 100000},
                "descendant_cleanup_evidence": {
                    "scope": "negresco-pe-0123456789abcdef01234567.scope",
                    "verified": True, "scope_quiescent": True,
                    "stop_request_accepted": False, "load_state": "not-found",
                    "scope_collected": True, "cgroup_unpopulated": True,
                    "active_state": "inactive", "sub_state": "dead"},
                "windows_binary_executed": False,
                "ghidra_executed": False},
            "windows_binary_executed": False,
            "ghidra": {
                "status": "PASS_REAL_ARCH_VM_GHIDRA",
                "sandbox": "bubblewrap", "pe_executed": False,
                "ghidra_functions": 18,
                "memory_max_bytes": 4294967296, "tasks_max": 128,
                "cpu_quota": 200000, "cpu_period": 100000,
                "ghidra_integrity": {
                    "verified": True, "release_sha256": GHIDRA_RELEASE_SHA256,
                    "matched_files": 100,
                    "symlinks_allowed": False,
                    "unexpected_files_allowed": False},
                "arch_isolation_probe": {
                    "status": "PASS_NATIVE_ARCH_BWRAP_PROBE",
                    "host_home_canary_hidden": True,
                    "network_namespace_separate": True,
                    "host_etc_hidden": True,
                    "usr_runtime_read_only": True,
                    "private_work_writable": True,
                    "inherited_host_fd_hidden": True},
                "arch_scoped_seccomp_probe": {
                    "status": "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP",
                    "scope": "negresco-pe-aaaaaaaaaaaaaaaaaaaaaaaa.scope",
                    "filter_compiled_after_guard": True,
                    "windows_pe_executed": False,
                    "ghidra_executed": False,
                    "sandbox_checks": [
                        "host_home_canary_hidden", "network_namespace_separate",
                        "host_etc_hidden", "usr_runtime_read_only",
                        "private_work_writable", "inherited_host_fd_hidden",
                        "seccomp_enforced"],
                    "cgroup_verification": {
                        "verification": "guard_verified_before_bwrap",
                        "memory_max_bytes": 4294967296,
                        "tasks_max": 128, "cpu_quota": 200000,
                        "cpu_period": 100000},
                    "scope_cleanup_evidence": {
                        "scope": "negresco-pe-aaaaaaaaaaaaaaaaaaaaaaaa.scope",
                        "verified": True, "scope_quiescent": True,
                        "stop_request_accepted": False,
                        "load_state": "not-found", "scope_collected": True,
                        "cgroup_unpopulated": True,
                        "active_state": "inactive", "sub_state": "dead"}},
                "arch_real_ghidra_with_both": {
                    "status": "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP",
                    "scope": "negresco-pe-bbbbbbbbbbbbbbbbbbbbbbbb.scope",
                    "scope_cleanup_verified": True,
                    "scope_stop_accepted": False,
                    "scope_cleanup_evidence": {
                        "scope": "negresco-pe-bbbbbbbbbbbbbbbbbbbbbbbb.scope",
                        "verified": True, "scope_quiescent": True,
                        "cgroup_unpopulated": True,
                        "stop_request_accepted": False,
                        "load_state": "not-found",
                        "active_state": "inactive", "sub_state": "dead",
                        "scope_collected": True},
                    "filter_compiled_inside_scope": True,
                    "quotas_verified_before_bwrap": {
                        "verification": "guard_verified_before_bwrap",
                        "memory_max_bytes": 4294967296,
                        "tasks_max": 128, "cpu_quota": 200000,
                        "cpu_period": 100000},
                    "decompiled_functions": 2,
                    "ghidra_functions_discovered": 18,
                    "bubblewrap": True,
                    "windows_binary_executed": False,
                    "ghidra_jvm_seccomp_evidence": {
                        "verified": True,
                        "measured_process": "ghidra_headless_jvm",
                        "measurement_source": "/proc/self/status",
                        "seccomp_mode": 2,
                        "filters_before_bwrap": 1,
                        "filters_in_ghidra": 2,
                        "additional_filters_observed": 1}}},
        }

    def write(self, report=None, path=None):
        return evidence.write_receipt_no_overwrite(
            self.report if report is None else report,
            self.dest if path is None else path, source_root=self.root,
            reviewer_challenge=self.challenge)

    def test_s1_29_report_producer_field_contracts_reject_injected_claims(self):
        locations = (
            (), ("environment",), ("cgroup",), ("cgroup_lifecycle",),
            ("cgroup_lifecycle", "quota_private_proof"),
            ("descendant_lifecycle",),
            ("descendant_lifecycle", "quota_private_proof"),
            ("ghidra",), ("ghidra", "ghidra_integrity"),
            ("ghidra", "arch_isolation_probe"),
            ("ghidra", "arch_scoped_seccomp_probe"),
            ("ghidra", "arch_scoped_seccomp_probe", "cgroup_verification"),
            ("ghidra", "arch_real_ghidra_with_both"),
            ("ghidra", "arch_real_ghidra_with_both",
             "quotas_verified_before_bwrap"),
            ("ghidra", "arch_real_ghidra_with_both",
             "ghidra_jvm_seccomp_evidence"),
        )
        for location in locations:
            for action in ("injected", "missing"):
                with self.subTest(location=location, action=action):
                    report = copy.deepcopy(self.report)
                    node = report
                    for key in location:
                        node = node[key]
                    if action == "injected":
                        node["independent_kernel_attestation"] = True
                    else:
                        node.pop(next(iter(node)))
                    with self.assertRaisesRegex(
                            evidence.AcceptanceReceiptError, "report fields"):
                        evidence.validate_native_acceptance_report(report)
                    with self.assertRaises(evidence.AcceptanceReceiptError):
                        self.write(report=report)
                    self.assertFalse(self.dest.exists())

    def test_s1_29_preflight_must_not_falsely_claim_cgroup_testing(self):
        for value in (True, "false", 0, None):
            with self.subTest(value=value):
                report = copy.deepcopy(self.report)
                report["environment"]["real_cgroup_test_executed"] = value
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_s1_29_local_review_rejects_rehashed_extra_security_claim(self):
        self.write()
        record = json.loads(self.dest.read_text(encoding="utf-8"))
        record["native_acceptance_report"][
            "independent_hypervisor_attestation"] = True
        record["report_sha256"] = hashlib.sha256(
            evidence._canonical(record["native_acceptance_report"])).hexdigest()
        self.dest.write_text(json.dumps(record), encoding="utf-8")
        self.dest.chmod(0o600)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge)

    def test_s1_27_rejects_conflicting_ghidra_inventories_before_receipt(self):
        for unexpected in (1, 17, 19, 2 ** 31, True, "18", None):
            with self.subTest(unexpected=unexpected):
                report = copy.deepcopy(self.report)
                report["ghidra"]["arch_real_ghidra_with_both"][
                    "ghidra_functions_discovered"] = unexpected
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    evidence.validate_native_acceptance_report(report)
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_s1_27_accepts_matching_inventories_with_partial_decompile(self):
        report = copy.deepcopy(self.report)
        report["ghidra"]["ghidra_functions"] = 37
        report["ghidra"]["arch_real_ghidra_with_both"][
            "ghidra_functions_discovered"] = 37
        # Some functions can legitimately fail decompilation; count of
        # successful decompilations need not equal the inventory count.
        report["ghidra"]["arch_real_ghidra_with_both"][
            "decompiled_functions"] = 1
        evidence.validate_native_acceptance_report(report)
        self.write(report=report)
        result = review.verify_local_receipt(
            self.dest, self.root, expected_challenge=self.challenge)
        self.assertEqual(result["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        self.assertFalse(result["independent_vm_attestation"])

    def test_s1_26_scope_cleanup_contract_accepts_both_kernel_outcomes(self):
        for collected in (False, True):
            report = copy.deepcopy(self.report)
            for location in (
                ("cgroup_lifecycle", "scope_cleanup_evidence"),
                ("descendant_lifecycle", "descendant_cleanup_evidence"),
                ("ghidra", "arch_scoped_seccomp_probe", "scope_cleanup_evidence"),
                ("ghidra", "arch_real_ghidra_with_both",
                 "scope_cleanup_evidence"),
            ):
                proof = report
                for item in location:
                    proof = proof[item]
                proof["load_state"] = "not-found" if collected else "loaded"
                proof["scope_collected"] = collected
                proof["stop_request_accepted"] = not collected
            report["ghidra"]["arch_real_ghidra_with_both"][
                "scope_stop_accepted"] = not collected
            with self.subTest(collected=collected):
                evidence.validate_native_acceptance_report(report)

    def test_s1_26_rejects_inconsistent_scope_cleanup_across_all_stages(self):
        locations = (
            ("cgroup_lifecycle", "scope_cleanup_evidence"),
            ("descendant_lifecycle", "descendant_cleanup_evidence"),
            ("ghidra", "arch_scoped_seccomp_probe", "scope_cleanup_evidence"),
            ("ghidra", "arch_real_ghidra_with_both",
             "scope_cleanup_evidence"),
        )
        mutations = (
            ("removed_scope", "scope", None),
            ("forged_status", "load_state", "running"),
            ("collected_false_for_not_found", "scope_collected", False),
            ("stop_not_boolean", "stop_request_accepted", "true"),
            ("active", "active_state", "active"),
            ("substate", "sub_state", "running"),
            ("not_quiescent", "scope_quiescent", False),
            ("not_verified", "verified", False),
            ("populated", "cgroup_unpopulated", False),
        )
        for location in locations:
            for case, key, value in mutations:
                with self.subTest(scope=location, case=case):
                    report = copy.deepcopy(self.report)
                    proof = report
                    for part in location:
                        proof = proof[part]
                    proof[key] = value
                    with self.assertRaises(
                            evidence.AcceptanceReceiptError):
                        evidence.validate_native_acceptance_report(report)
                    with self.assertRaises(
                            evidence.AcceptanceReceiptError):
                        self.write(report=report)
                    self.assertFalse(self.dest.exists())

    def test_s1_26_rejects_ghidra_stop_summary_disagreeing_with_cleanup(self):
        report = copy.deepcopy(self.report)
        report["ghidra"]["arch_real_ghidra_with_both"][
            "scope_stop_accepted"] = True
        with self.assertRaisesRegex(evidence.AcceptanceReceiptError,
                                    "acknowledgement"):
            self.write(report=report)
        self.assertFalse(self.dest.exists())

    def test_s1_26_rejects_missing_or_extra_cleanup_keys(self):
        for action in ("missing", "unexpected"):
            report = copy.deepcopy(self.report)
            proof = report["cgroup_lifecycle"]["scope_cleanup_evidence"]
            if action == "missing":
                proof.pop("load_state")
            else:
                proof["verified_by_external_hypervisor"] = True
            with self.subTest(action=action):
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_s1_22_rejects_missing_or_contradictory_isolation_evidence(self):
        mutations = [
            ("vm.root", ("environment", "root"), True),
            ("vm.user_bus", ("environment", "systemd_user_bus"), False),
            ("ghidra.status", ("ghidra", "status"), "PASS_MOCKED_ONLY"),
            ("ghidra.sandbox", ("ghidra", "sandbox"), "none"),
            ("ghidra.pe_executed", ("ghidra", "pe_executed"), True),
            ("ghidra.functions", ("ghidra", "ghidra_functions"), 0),
            ("ghidra.memory", ("ghidra", "memory_max_bytes"), 9 * 1024 ** 3),
            ("ghidra.integrity.sha",
             ("ghidra", "ghidra_integrity", "release_sha256"), "0" * 64),
            ("ghidra.integrity.extra",
             ("ghidra", "ghidra_integrity", "unexpected_files_allowed"), True),
            ("ghidra.integrity.count",
             ("ghidra", "ghidra_integrity", "matched_files"), 0),
            ("bubblewrap.network",
             ("ghidra", "arch_isolation_probe", "network_namespace_separate"), False),
            ("bubblewrap.fd",
             ("ghidra", "arch_isolation_probe", "inherited_host_fd_hidden"), None),
            ("bubblewrap.status",
             ("ghidra", "arch_isolation_probe", "status"), "FAKE_PASS"),
            ("seccomp.after_guard",
             ("ghidra", "arch_scoped_seccomp_probe", "filter_compiled_after_guard"), False),
            ("seccomp.sandbox",
             ("ghidra", "arch_scoped_seccomp_probe", "sandbox_checks"), []),
            ("seccomp.windows_pe",
             ("ghidra", "arch_scoped_seccomp_probe", "windows_pe_executed"), True),
            ("seccomp.cleanup",
             ("ghidra", "arch_scoped_seccomp_probe", "scope_cleanup_evidence",
              "active_state"), "active"),
            ("descendant.windows",
             ("descendant_lifecycle", "windows_binary_executed"), True),
            ("descendant.ghidra",
             ("descendant_lifecycle", "ghidra_executed"), True),
            ("combined.bubblewrap",
             ("ghidra", "arch_real_ghidra_with_both", "bubblewrap"), False),
            ("combined.windows",
             ("ghidra", "arch_real_ghidra_with_both", "windows_binary_executed"), True),
            ("combined.functions",
             ("ghidra", "arch_real_ghidra_with_both", "ghidra_functions_discovered"), 0),
            ("combined.decompile_overcount",
             ("ghidra", "arch_real_ghidra_with_both", "decompiled_functions"), 19),
        ]
        for title, path, value in mutations:
            with self.subTest(title=title):
                report = copy.deepcopy(self.report)
                target = report
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    evidence.validate_native_acceptance_report(report)
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_s1_22_rejects_missing_isolation_and_integrity_objects(self):
        for parent, field in (
            ("ghidra", "arch_isolation_probe"),
            ("ghidra", "ghidra_integrity"),
            ("ghidra", "arch_real_ghidra_with_both"),
        ):
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report[parent].pop(field)
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_s1_24_rejects_replayed_or_unexpected_challenge(self):
        self.write()
        wrong = "fedcba9876543210" * 4
        with self.assertRaisesRegex(
                review.ReceiptReviewError, "challenge"):
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=wrong)
        record = json.loads(self.dest.read_text(encoding="utf-8"))
        for changed in (None, "", "0" * 64, wrong, "A" * 64, "f" * 63, 17):
            with self.subTest(changed=changed):
                modified = copy.deepcopy(record)
                if changed is None:
                    modified.pop("reviewer_challenge")
                else:
                    modified["reviewer_challenge"] = changed
                self.dest.write_text(json.dumps(modified), encoding="utf-8")
                self.dest.chmod(0o600)
                with self.assertRaises(review.ReceiptReviewError):
                    review.verify_local_receipt(
                        self.dest, self.root,
                        expected_challenge=self.challenge)

    def test_s1_24_invalid_or_missing_writer_challenges_fail_before_writing(self):
        for invalid in (None, "", "0" * 64, "A" * 64, "x" * 64,
                        "a" * 63, 1234, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    evidence.write_receipt_no_overwrite(
                        self.report, self.dest, source_root=self.root,
                        reviewer_challenge=invalid)
                self.assertFalse(self.dest.exists())

    def test_s1_24_old_v1_receipt_is_not_accepted_as_fresh_v2(self):
        self.write()
        record = json.loads(self.dest.read_text(encoding="utf-8"))
        record["schema"] = "negresco_native_arch_vm_local_receipt_v1"
        record.pop("reviewer_challenge")
        self.dest.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge)

    def test_s1_24_reviewer_challenge_does_not_claim_independent_vm(self):
        self.write()
        result = review.verify_local_receipt(
            self.dest, self.root, expected_challenge=self.challenge)
        self.assertTrue(result["reviewer_challenge_correlated"])
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["independent_vm_attestation"])

    def test_private_receipt_records_source_hashes_without_claiming_signature(self):
        written = self.write()
        self.assertEqual(written["path"], str(self.dest))
        saved = self.dest.read_bytes()
        self.assertEqual(written["receipt_sha256"],
                         hashlib.sha256(saved).hexdigest())
        payload = json.loads(saved)
        self.assertEqual(payload["schema"],
                         "negresco_native_arch_vm_local_receipt_v2")
        self.assertEqual(payload["reviewer_challenge"], self.challenge)
        self.assertEqual(payload["security_classification"],
                         "LOCAL_SELF_REPORT_NOT_SIGNED")
        self.assertEqual(payload["native_acceptance_report"], self.report)
        self.assertEqual(payload["source_file_hashes"]["tools/synthetic.py"]["sha256"],
                         hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(stat.S_IMODE(self.dest.stat().st_mode), 0o600)
        self.assertEqual(payload["report_sha256"],
                         hashlib.sha256(evidence._canonical(self.report)).hexdigest())

    def test_independent_offline_receipt_audit_matches_private_source(self):
        self.write()
        result = review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)
        self.assertEqual(result["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        self.assertEqual(result["source_files_rechecked"], 1)
        self.assertEqual(result["security_classification"],
                         "UNSIGNED_NOT_INDEPENDENT_VM_ATTESTATION")
        self.assertFalse(result["native_kernel_execution_independently_verified"])
        self.assertFalse(result["windows_binary_executed_by_reviewer"])

    def test_offline_audit_detects_source_drift_and_symlink(self):
        self.write()
        self.source.write_text("print('modified source')\n", encoding="utf-8")
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)
        self.source.unlink()
        unrelated = self.root / "unrelated.txt"
        unrelated.write_text("print('harmless fixture')\n", encoding="utf-8")
        self.source.symlink_to(unrelated)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)

    def test_offline_audit_rejects_changed_report_and_manifest(self):
        self.write()
        original = json.loads(self.dest.read_text(encoding="utf-8"))
        for mutation in ("report", "hash", "manifest", "classification"):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(original)
                if mutation == "report":
                    record["native_acceptance_report"]["windows_binary_executed"] = True
                elif mutation == "hash":
                    record["report_sha256"] = "0" * 64
                elif mutation == "manifest":
                    record["source_file_hashes"]["tools/synthetic.py"]["sha256"] = "f" * 64
                else:
                    record["security_classification"] = "INDEPENDENT_VM_SIGNED"
                self.dest.write_text(json.dumps(record), encoding="utf-8")
                self.dest.chmod(0o600)
                with self.assertRaises(review.ReceiptReviewError):
                    review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)
        self.assertTrue(self.dest.exists())

    def test_offline_audit_rejects_duplicate_json_keys_or_nonfinite(self):
        self.write()
        source = self.dest.read_text(encoding="utf-8")
        for injected in (
                source.replace('"schema":', '"schema":"duplicate","schema":', 1),
                source.replace('"recorded_at_utc":', '"noise":NaN,"recorded_at_utc":', 1),
                source.replace('"recorded_at_utc":', '"noise":Infinity,"recorded_at_utc":', 1),
        ):
            self.dest.write_text(injected, encoding="utf-8")
            self.dest.chmod(0o600)
            with self.assertRaises(review.ReceiptReviewError):
                review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)

    def test_s1_32_receipt_uses_snapshot_not_mutable_report_alias(self):
        original = copy.deepcopy(self.report)
        receipt = evidence.build_receipt(
            self.report, source_root=self.root,
            reviewer_challenge=self.challenge)
        self.assertEqual(receipt["native_acceptance_report"], original)
        self.assertIsNot(receipt["native_acceptance_report"], self.report)
        self.assertIsNot(
            receipt["native_acceptance_report"]["ghidra"],
            self.report["ghidra"])
        # A later change to a nested object must not change hashed contents.
        self.report["environment"]["vm_confirmed"] = False
        self.report["ghidra"]["arch_real_ghidra_with_both"][
            "decompiled_functions"] = 0
        self.report["independent_kernel_attestation"] = True
        self.assertEqual(receipt["native_acceptance_report"], original)
        self.assertEqual(
            receipt["report_sha256"],
            hashlib.sha256(evidence._canonical(
                receipt["native_acceptance_report"])).hexdigest())
        evidence.validate_native_acceptance_report(
            receipt["native_acceptance_report"])

    def test_s1_32_validation_uses_the_same_canonical_snapshot(self):
        original = copy.deepcopy(self.report)
        checked = []
        real_validator = evidence.validate_native_acceptance_report

        def mutate_source_and_validate(snapshot):
            self.report["environment"]["vm_confirmed"] = False
            self.report["ghidra"]["ghidra_functions"] = 0
            checked.append(snapshot)
            real_validator(snapshot)

        with mock.patch.object(
                evidence, "validate_native_acceptance_report",
                side_effect=mutate_source_and_validate):
            receipt = evidence.build_receipt(
                self.report, source_root=self.root,
                reviewer_challenge=self.challenge)
        self.assertEqual(checked, [original])
        self.assertIs(checked[0], receipt["native_acceptance_report"])
        self.assertEqual(
            receipt["report_sha256"],
            hashlib.sha256(evidence._canonical(original)).hexdigest())

    def test_s1_32_rejects_cyclic_report_as_controlled_error(self):
        invalid = copy.deepcopy(self.report)
        invalid["native_report_loop"] = invalid
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.build_receipt(
                invalid, source_root=self.root,
                reviewer_challenge=self.challenge)
        self.assertFalse(self.dest.exists())

    def test_s1_30_offline_reviewer_refuses_fifo_receipt_without_hanging(self):
        # FIFO has no writer: a blocking read open would never reach fstat.
        fifo = self.private / "fifo-receipt.json"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(
                fifo, self.root, expected_challenge=self.challenge)

    def test_s1_30_writer_refuses_fifo_source_without_hanging(self):
        self.source.unlink()
        os.mkfifo(self.source, 0o600)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write()
        self.assertFalse(self.dest.exists())

    def test_s1_30_offline_reviewer_refuses_fifo_source_without_hanging(self):
        self.write()
        self.source.unlink()
        os.mkfifo(self.source, 0o600)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge)

    def test_offline_audit_refuses_untrusted_private_paths(self):
        self.write()
        alias = self.root / "linked-proof"
        alias.symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(alias / self.dest.name, self.root, expected_challenge=self.challenge)
        self.private.chmod(0o755)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)
        self.private.chmod(0o700)
        self.dest.chmod(0o644)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)

    def test_offline_review_and_writer_refuse_symlinked_receipt_ancestor(self):
        self.write()
        outer = self.root / "actual-parent"
        outer.mkdir(mode=0o700)
        nested = outer / "private"
        nested.mkdir(mode=0o700)
        copied = nested / "copied.json"
        copied.write_bytes(self.dest.read_bytes())
        copied.chmod(0o600)
        self.assertEqual(review.verify_local_receipt(copied, self.root, expected_challenge=self.challenge)["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        alias = self.root / "linked-ancestor"
        alias.symlink_to(outer, target_is_directory=True)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(alias / "private" / "copied.json",
                                        self.root, expected_challenge=self.challenge)
        bad_dest = alias / "private" / "new.json"
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.write_receipt_no_overwrite(
                self.report, bad_dest, source_root=self.root, reviewer_challenge=self.challenge)
        self.assertFalse((nested / "new.json").exists())

    def test_offline_review_and_writer_refuse_source_root_ancestor_symlink(self):
        self.write()
        outer = self.root / "actual-sources"
        checkout = outer / "checkout"
        (checkout / "tools").mkdir(parents=True, mode=0o700)
        (checkout / "tools" / "synthetic.py").write_bytes(self.source.read_bytes())
        self.assertEqual(review.verify_local_receipt(self.dest, checkout, expected_challenge=self.challenge)["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        alias = self.root / "linked-sources"
        alias.symlink_to(outer, target_is_directory=True)
        bad_root = alias / "checkout"
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, bad_root, expected_challenge=self.challenge)
        bad_dest = self.private / "another.json"
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.write_receipt_no_overwrite(
                self.report, bad_dest, source_root=bad_root, reviewer_challenge=self.challenge)
        self.assertFalse(bad_dest.exists())

    def test_writer_rejects_symlink_in_source_manifest_directory(self):
        actual_tools = self.root / "actual-tools"
        (self.root / "tools").rename(actual_tools)
        (self.root / "tools").symlink_to(actual_tools, target_is_directory=True)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write()
        self.assertFalse(self.dest.exists())

    def test_offline_audit_rejects_oversized_receipt(self):
        self.write()
        with self.dest.open("ab") as out:
            out.write(b" " * review.MAX_RECEIPT_BYTES)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root, expected_challenge=self.challenge)

    def test_offline_reviewer_cli_uses_precise_non_attestation_status(self):
        self.write()
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        stdout = StringIO()
        with redirect_stdout(stdout):
            success = review.main([
                "--receipt", str(self.dest),
                "--source-root", str(self.root),
                "--expected-challenge", self.challenge])
        self.assertEqual(success, 0)
        self.assertFalse(json.loads(stdout.getvalue())[
            "native_kernel_execution_independently_verified"])
        stderr = StringIO()
        with redirect_stderr(stderr):
            failure = review.main([
                "--receipt", str(self.root / "missing.json"),
                "--source-root", str(self.root),
                "--expected-challenge", self.challenge])
        self.assertEqual(failure, 2)
        self.assertEqual(json.loads(stderr.getvalue())["status"],
                         "REJECTED_LOCAL_RECEIPT")


    def test_s1_37_external_receipt_pin_accepts_exact_prior_digest(self):
        issued = self.write()
        expected = issued["receipt_sha256"]
        self.assertEqual(expected, hashlib.sha256(
            self.dest.read_bytes()).hexdigest())
        pinned = review.verify_local_receipt(
            self.dest, self.root, expected_challenge=self.challenge,
            expected_receipt_sha256=expected)
        self.assertEqual(pinned["receipt_sha256"], expected)
        self.assertTrue(pinned["external_receipt_sha256_pin_matched"])
        unpinned = review.verify_local_receipt(
            self.dest, self.root, expected_challenge=self.challenge)
        self.assertFalse(unpinned["external_receipt_sha256_pin_matched"])
        self.assertFalse(pinned["independent_vm_attestation"])
        self.assertFalse(pinned["native_kernel_execution_independently_verified"])

    def test_s1_37_rejects_replaced_self_consistent_receipt_with_rehashed_report(self):
        issued = self.write()
        original_digest = issued["receipt_sha256"]
        record = json.loads(self.dest.read_text(encoding="utf-8"))
        combined = record["native_acceptance_report"]["ghidra"][
            "arch_real_ghidra_with_both"]
        self.assertEqual(combined["decompiled_functions"], 2)
        # A forged local report still satisfies its own evidence contracts.
        combined["decompiled_functions"] = 3
        record["report_sha256"] = hashlib.sha256(
            evidence._canonical(record["native_acceptance_report"])).hexdigest()
        self.dest.write_bytes(evidence._canonical(record))
        self.dest.chmod(0o600)
        self.assertNotEqual(
            hashlib.sha256(self.dest.read_bytes()).hexdigest(), original_digest)
        # A local consistency check alone cannot notice self-consistent lies.
        unpinned = review.verify_local_receipt(
            self.dest, self.root, expected_challenge=self.challenge)
        self.assertEqual(unpinned["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        with self.assertRaisesRegex(
                review.ReceiptReviewError, "independently retained"):
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge,
                expected_receipt_sha256=original_digest)

    def test_s1_37_external_pin_rejects_wrong_or_invalid_digest(self):
        self.write()
        actual = hashlib.sha256(self.dest.read_bytes()).hexdigest()
        for invalid in ("0" * 64, "f" * 63, "G" * 64, "A" * 64,
                        "", 42, True, b"f" * 64, "f" * 65):
            with self.subTest(invalid=invalid):
                with self.assertRaises(review.ReceiptReviewError):
                    review.verify_local_receipt(
                        self.dest, self.root, expected_challenge=self.challenge,
                        expected_receipt_sha256=invalid)
        self.assertEqual(
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge,
                expected_receipt_sha256=actual)[
                    "external_receipt_sha256_pin_matched"], True)

    def test_s1_37_bad_external_pin_refused_before_receipt_read(self):
        with mock.patch.object(
                review, "_read_private_receipt",
                side_effect=AssertionError("must not open receipt")):
            with self.assertRaisesRegex(
                    review.ReceiptReviewError, "64 lowercase hex"):
                review.verify_local_receipt(
                    self.dest, self.root, expected_challenge=self.challenge,
                    expected_receipt_sha256="not-a-digest")

    def test_s1_37_cli_checks_external_pin_and_reports_explicit_match(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        issued = self.write()
        base_args = [
            "--receipt", str(self.dest), "--source-root", str(self.root),
            "--expected-challenge", self.challenge]
        output = StringIO()
        with redirect_stdout(output):
            status = review.main(
                base_args + ["--expected-receipt-sha256",
                             issued["receipt_sha256"]])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result["external_receipt_sha256_pin_matched"])
        self.assertFalse(result["independent_vm_attestation"])
        error = StringIO()
        with redirect_stderr(error):
            code = review.main(
                base_args + ["--expected-receipt-sha256", "f" * 64])
        self.assertEqual(code, 2)
        self.assertEqual(
            json.loads(error.getvalue())["status"], "REJECTED_LOCAL_RECEIPT")

    def test_s1_36_reviewer_refuses_valid_json_in_unpublished_stage(self):
        self.write()
        staged = self.private / (
            ".negresco-receipt-" + "e" * 32 + ".tmp")
        staged.write_bytes(self.dest.read_bytes())
        staged.chmod(0o600)
        with self.assertRaisesRegex(
                review.ReceiptReviewError, "Unpublished temporary stage"):
            review.verify_local_receipt(
                staged, self.root, expected_challenge=self.challenge)
        # A final named receipt still validates normally.
        self.assertEqual(
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge
            )["status"], "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")

    def test_s1_36_reviewer_refuses_directory_busy_with_writer_lock(self):
        import fcntl
        self.write()
        holder = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(review.ReceiptReviewError):
                review.verify_local_receipt(
                    self.dest, self.root, expected_challenge=self.challenge)
            self.assertTrue(self.dest.is_file())
        finally:
            os.close(holder)
        self.assertEqual(
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge
            )["status"], "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")

    def test_s1_36_shared_reader_lock_held_while_reading_receipt(self):
        import fcntl
        self.write()
        original_read = os.read
        expected = self.dest.stat().st_ino
        observed = []

        def check_lock(fd, amount):
            if os.fstat(fd).st_ino == expected:
                competing = os.open(
                    self.private, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(
                            competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    observed.append("shared-lock-protected-read")
                finally:
                    os.close(competing)
            return original_read(fd, amount)

        with mock.patch.object(review.os, "read", side_effect=check_lock):
            result = review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge)
        self.assertEqual(result["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        self.assertEqual(observed, ["shared-lock-protected-read"])

    def test_s1_36_reviewer_rejects_replaced_receipt_name_same_bytes(self):
        self.write()
        replacement = self.private / "replacement.json"
        replacement.write_bytes(self.dest.read_bytes())
        replacement.chmod(0o600)
        original_read = os.read
        old_inode = self.dest.stat().st_ino
        swapped = []

        def swap_name_while_reading(fd, amount):
            if os.fstat(fd).st_ino == old_inode and not swapped:
                os.replace(replacement, self.dest)
                swapped.append(True)
            return original_read(fd, amount)

        with mock.patch.object(
                review.os, "read", side_effect=swap_name_while_reading):
            with self.assertRaisesRegex(
                    review.ReceiptReviewError, "name or inode changed"):
                review.verify_local_receipt(
                    self.dest, self.root, expected_challenge=self.challenge)
        self.assertEqual(swapped, [True])
        self.assertTrue(self.dest.exists())
        self.assertFalse(replacement.exists())

    def test_s1_36_reviewer_rejects_replaced_source_name_same_bytes(self):
        replacement = self.root / "tools" / "replacement.py"
        replacement.write_bytes(self.source.read_bytes())
        original_read = os.read
        old_inode = self.source.stat().st_ino
        swapped = []

        def swap_source_while_reading(fd, amount):
            if os.fstat(fd).st_ino == old_inode and not swapped:
                os.replace(replacement, self.source)
                swapped.append(True)
            return original_read(fd, amount)

        with mock.patch.object(
                review.os, "read", side_effect=swap_source_while_reading):
            with self.assertRaisesRegex(
                    review.ReceiptReviewError, "name or inode changed"):
                review._read_source(self.root, "tools/synthetic.py")
        self.assertEqual(swapped, [True])
        self.assertFalse(replacement.exists())

    def test_s1_35_busy_directory_lock_blocks_write_without_creating_stage(self):
        import fcntl
        owner = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(
                    evidence.AcceptanceReceiptError, "directory busy"):
                self.write()
            self.assertFalse(self.dest.exists())
            self.assertEqual(list(self.private.iterdir()), [])
        finally:
            os.close(owner)
        self.write()
        self.assertTrue(self.dest.is_file())

    def test_s1_35_busy_writer_blocks_cleanup_preview_and_apply(self):
        import fcntl
        stage = self.private / (".negresco-receipt-" + "1" * 32 + ".tmp")
        stage.write_bytes(b"unfinished")
        stage.chmod(0o600)
        now = stage.stat().st_ctime_ns + 50 * 3600 * 10 ** 9
        owner = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with mock.patch.object(evidence.time, "time_ns", return_value=now):
                for apply in (False, True):
                    with self.subTest(apply=apply):
                        with self.assertRaisesRegex(
                                evidence.AcceptanceReceiptError,
                                "directory busy"):
                            evidence.cleanup_orphan_receipt_stages(
                                self.private, apply=apply)
                        self.assertTrue(stage.exists())
        finally:
            os.close(owner)
        with mock.patch.object(evidence.time, "time_ns", return_value=now):
            result = evidence.cleanup_orphan_receipt_stages(
                self.private, apply=True)
        self.assertEqual(result["removed_stages"], [stage.name])

    def test_s1_35_shared_preview_allows_previews_but_blocks_mutations(self):
        import fcntl
        reader = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(reader, fcntl.LOCK_SH | fcntl.LOCK_NB)
            self.assertEqual(
                evidence.cleanup_orphan_receipt_stages(self.private)[
                    "status"], "STAGE_CLEANUP_PREVIEW")
            with self.assertRaisesRegex(
                    evidence.AcceptanceReceiptError, "directory busy"):
                evidence.cleanup_orphan_receipt_stages(
                    self.private, apply=True)
            with self.assertRaisesRegex(
                    evidence.AcceptanceReceiptError, "directory busy"):
                self.write()
            self.assertFalse(self.dest.exists())
        finally:
            os.close(reader)

    def test_s1_35_writer_lock_covers_atomic_publication(self):
        import fcntl
        real_link = os.link
        observed = []

        def inspect_lock_during_link(src, dst, **kwargs):
            second = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(
                        second, fcntl.LOCK_EX | fcntl.LOCK_NB)
                observed.append("writer-exclusive")
            finally:
                os.close(second)
            return real_link(src, dst, **kwargs)

        with mock.patch.object(evidence.os, "link",
                               side_effect=inspect_lock_during_link):
            self.write()
        self.assertEqual(observed, ["writer-exclusive"])
        self.assertTrue(self.dest.exists())
        second = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(second)

    def test_s1_35_cleanup_lock_covers_removal(self):
        import fcntl
        stage = self.private / (".negresco-receipt-" + "2" * 32 + ".tmp")
        stage.write_bytes(b"old incomplete receipt")
        stage.chmod(0o600)
        now = stage.stat().st_ctime_ns + 50 * 3600 * 10 ** 9
        real_unlink = os.unlink
        observed = []

        def inspect_lock_during_unlink(name, *args, **kwargs):
            if name == stage.name:
                second = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(
                            second, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    observed.append("cleanup-exclusive")
                finally:
                    os.close(second)
            return real_unlink(name, *args, **kwargs)

        with (mock.patch.object(evidence.time, "time_ns", return_value=now),
              mock.patch.object(evidence.os, "unlink",
                                side_effect=inspect_lock_during_unlink)):
            result = evidence.cleanup_orphan_receipt_stages(
                self.private, apply=True)
        self.assertEqual(observed, ["cleanup-exclusive"])
        self.assertEqual(result["removed_stages"], [stage.name])
        self.assertFalse(stage.exists())

    def test_s1_34_preview_then_explicit_cleanup_of_old_single_link_stage(self):
        from pe_receipt_stage_cleanup import main
        stage = self.private / (".negresco-receipt-" + "a" * 32 + ".tmp")
        stage.write_bytes(b'{"partially_written":')
        stage.chmod(0o600)
        final = self.private / "legitimate.json"
        final.write_bytes(b"real final receipt should never be cleaned")
        final.chmod(0o600)
        now = max(stage.stat().st_ctime_ns, stage.stat().st_mtime_ns)
        with mock.patch.object(evidence.time, "time_ns",
                               return_value=now + 25 * 3600 * 10 ** 9):
            preview = evidence.cleanup_orphan_receipt_stages(self.private)
            self.assertEqual(preview["status"], "STAGE_CLEANUP_PREVIEW")
            self.assertEqual(preview["eligible_stages"], [stage.name])
            self.assertEqual(preview["removed_stages"], [])
            self.assertTrue(stage.exists())
            applied = evidence.cleanup_orphan_receipt_stages(
                self.private, apply=True)
        self.assertEqual(applied["removed_stages"], [stage.name])
        self.assertFalse(stage.exists())
        self.assertEqual(final.read_bytes(), b"real final receipt should never be cleaned")

    def test_s1_34_rejects_symlink_hardlink_public_and_similar_names(self):
        target = self.root / "important.txt"
        target.write_text("protected", encoding="utf-8")
        symlink = self.private / (".negresco-receipt-" + "b" * 32 + ".tmp")
        symlink.symlink_to(target)
        hardlink = self.private / (".negresco-receipt-" + "c" * 32 + ".tmp")
        os.link(target, hardlink)
        nonprivate = self.private / (".negresco-receipt-" + "d" * 32 + ".tmp")
        nonprivate.write_bytes(b"not owned by writer")
        nonprivate.chmod(0o644)
        odd = self.private / ".negresco-receipt-not-a-token.tmp"
        odd.write_bytes(b"unrelated")
        now = max(x.stat().st_ctime_ns for x in (target, hardlink, nonprivate, odd))
        with mock.patch.object(evidence.time, "time_ns",
                               return_value=now + 48 * 3600 * 10 ** 9):
            result = evidence.cleanup_orphan_receipt_stages(
                self.private, apply=True)
        self.assertEqual(result["removed_stages"], [])
        self.assertEqual(target.read_text(encoding="utf-8"), "protected")
        self.assertTrue(symlink.is_symlink())
        self.assertTrue(hardlink.exists())
        self.assertTrue(nonprivate.exists())
        self.assertTrue(odd.exists())

    def test_s1_34_skips_young_stage_and_changed_inode(self):
        stage = self.private / (".negresco-receipt-" + "f" * 32 + ".tmp")
        stage.write_bytes(b"in progress")
        stage.chmod(0o600)
        self.assertEqual(evidence.cleanup_orphan_receipt_stages(
            self.private, apply=True)["removed_stages"], [])
        original_stat = os.stat

        def replace_before_final_check(name, *args, **kwargs):
            if (name == stage.name and kwargs.get("follow_symlinks") is False
                    and kwargs.get("dir_fd") is not None):
                # First directory scan sees old inode. The second check
                # catches a replacement that must never be deleted.
                if not hasattr(replace_before_final_check, "saw"):
                    replace_before_final_check.saw = True
                else:
                    stage.unlink()
                    stage.write_bytes(b"replacement")
                    stage.chmod(0o600)
                    return original_stat(name, *args, **kwargs)
            return original_stat(name, *args, **kwargs)

        past = stage.stat().st_ctime_ns + 48 * 3600 * 10 ** 9
        with (mock.patch.object(evidence.time, "time_ns", return_value=past),
              mock.patch.object(evidence.os, "stat",
                                side_effect=replace_before_final_check)):
            result = evidence.cleanup_orphan_receipt_stages(
                self.private, apply=True)
        self.assertEqual(result["removed_stages"], [])
        self.assertEqual(stage.read_bytes(), b"replacement")

    def test_s1_34_rejects_unsafe_cleanup_options_and_paths(self):
        for args in (
                {"min_age_seconds": 0}, {"min_age_seconds": True},
                {"min_age_seconds": 366 * 86400}, {"apply": "yes"}):
            with self.subTest(args=args):
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    evidence.cleanup_orphan_receipt_stages(
                        self.private, **args)
        public = self.root / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.cleanup_orphan_receipt_stages(public)
        alias = self.root / "alias-stage"
        alias.symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.cleanup_orphan_receipt_stages(alias)

    def test_s1_34_cli_requires_explicit_apply_and_absolute_private_path(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from pe_receipt_stage_cleanup import main
        with redirect_stdout(StringIO()) as capture:
            self.assertEqual(main([
                "--private-directory", str(self.private)]), 0)
        self.assertEqual(json.loads(capture.getvalue())["status"],
                         "STAGE_CLEANUP_PREVIEW")
        with redirect_stderr(StringIO()):
            self.assertEqual(main([
                "--private-directory", str(self.private),
                "--min-age-hours", "1", "--apply"]), 2)
            self.assertEqual(main([
                "--private-directory", "relative-path", "--apply"]), 2)

    def test_s1_33_publishes_only_complete_fsynced_private_receipt(self):
        original_link = os.link
        original_fsync = os.fsync
        steps = []

        def watch_fsync(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                self.assertFalse(self.dest.exists())
                temp_files = list(self.private.glob(".negresco-receipt-*.tmp"))
                self.assertEqual(len(temp_files), 1)
                self.assertEqual(
                    json.loads(temp_files[0].read_text(encoding="utf-8"))[
                        "schema"], "negresco_native_arch_vm_local_receipt_v2")
                steps.append("file-fsync")
            else:
                steps.append("directory-fsync")
            return original_fsync(fd)

        def watch_link(src, dst, **options):
            self.assertEqual(steps, ["file-fsync"])
            self.assertFalse(self.dest.exists())
            self.assertEqual(dst, self.dest.name)
            output = original_link(src, dst, **options)
            steps.append("published")
            return output

        with (mock.patch.object(evidence.os, "fsync", side_effect=watch_fsync),
              mock.patch.object(evidence.os, "link", side_effect=watch_link)):
            receipt = self.write()
        self.assertEqual(steps, [
            "file-fsync", "published", "directory-fsync"])
        self.assertEqual(receipt["record_type"], "LOCAL_SELF_REPORT_NOT_SIGNED")
        self.assertEqual(stat.S_IMODE(self.dest.stat().st_mode), 0o600)
        self.assertEqual(list(self.private.glob(".negresco-receipt-*.tmp")), [])
        self.assertEqual(
            review.verify_local_receipt(
                self.dest, self.root, expected_challenge=self.challenge
            )["status"], "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")

    def test_s1_33_refuses_publish_failure_and_cleans_staging_file(self):
        with mock.patch.object(evidence.os, "link",
                               side_effect=OSError("injected link failure")):
            with self.assertRaises(evidence.AcceptanceReceiptError):
                self.write()
        self.assertFalse(self.dest.exists())
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_33_directory_sync_failure_rolls_back_published_receipt(self):
        real_fsync = os.fsync
        seen = []

        def fail_directory_sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                seen.append("directory")
                raise OSError("injected directory fsync failure")
            return real_fsync(fd)

        with mock.patch.object(evidence.os, "fsync",
                               side_effect=fail_directory_sync):
            with self.assertRaises(evidence.AcceptanceReceiptError):
                self.write()
        self.assertGreaterEqual(len(seen), 1)
        self.assertFalse(self.dest.exists())
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_33_file_sync_failure_never_publishes_receipt(self):
        real_fsync = os.fsync

        def fail_file_sync(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("injected file fsync failure")
            return real_fsync(fd)

        with mock.patch.object(evidence.os, "fsync",
                               side_effect=fail_file_sync):
            with self.assertRaises(evidence.AcceptanceReceiptError):
                self.write()
        self.assertFalse(self.dest.exists())
        self.assertEqual(list(self.private.iterdir()), [])

    def test_s1_33_concurrent_existing_receipt_never_overwritten(self):
        # Another process can win the final name while the candidate is
        # staged. Hard-link publication must fail closed without clobbering it.
        original_link = os.link
        def competing_receipt(src, dst, **options):
            self.dest.write_text("other writer won", encoding="utf-8")
            self.dest.chmod(0o600)
            return original_link(src, dst, **options)

        with mock.patch.object(evidence.os, "link",
                               side_effect=competing_receipt):
            with self.assertRaises(evidence.AcceptanceReceiptError):
                self.write()
        self.assertEqual(self.dest.read_text(encoding="utf-8"),
                         "other writer won")
        self.assertEqual(list(self.private.glob(".negresco-receipt-*.tmp")), [])

    def test_does_not_overwrite_existing_receipt(self):
        self.write()
        original = self.dest.read_bytes()
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write()
        self.assertEqual(self.dest.read_bytes(), original)

    def test_rejects_nonprivate_or_relative_destination(self):
        public = self.root / "public"
        public.mkdir(mode=0o755)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write(path=public / "proof.json")
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write(path=Path("relative.json"))
        self.assertFalse((public / "proof.json").exists())

    def test_rejects_symlinked_destination_and_source(self):
        target = self.root / "unrelated.txt"
        target.write_text("never change", encoding="utf-8")
        self.dest.symlink_to(target)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write()
        self.assertEqual(target.read_text(encoding="utf-8"), "never change")
        self.dest.unlink()
        self.source.unlink()
        self.source.symlink_to(target)
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write()
        self.assertFalse(self.dest.exists())

    def test_refuses_mocked_ci_or_missing_native_vm_proofs(self):
        cases = (
            ("environment", {
                "status": "ARCH_VM_PREFLIGHT_PASSED",
                "vm_confirmed": False, "container": True}),
            ("descendants_terminated", False),
            ("windows_binary_executed", True),
            ("status", "PASS_REAL_GHIDRA_BRIDGE_MOCKED_CGROUP_ONLY"),
        )
        for key, value in cases:
            with self.subTest(key=key):
                report = {**self.report, key: value}
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_refuses_missing_real_jvm_cgroup_or_decompilation(self):
        original = self.report["ghidra"]["arch_real_ghidra_with_both"]
        for key, value in (
                ("scope_cleanup_verified", False),
                ("scope_cleanup_evidence", {
                    "verified": False, "scope_quiescent": False,
                    "cgroup_unpopulated": False,
                    "active_state": "active", "sub_state": "running"}),
                ("decompiled_functions", 0),
                ("quotas_verified_before_bwrap", {}),
                ("ghidra_jvm_seccomp_evidence", {
                    "verified": True,
                    "measured_process": "ghidra_headless_jvm",
                    "seccomp_mode": 2,
                    "filters_before_bwrap": 3,
                    "filters_in_ghidra": 3}),
        ):
            with self.subTest(key=key):
                changed = dict(original)
                changed[key] = value
                report = {**self.report, "ghidra": {
                    **self.report["ghidra"],
                    "arch_real_ghidra_with_both": changed}}
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
        self.assertFalse(self.dest.exists())

    def test_refuses_missing_or_fake_descendant_cleanup_without_writing(self):
        base = self.report["descendant_lifecycle"]
        for modified in (
                None,
                {"status": "PASS_NATIVE_ARCH_DESCENDANTS"},
                {**base, "systemd_stop_succeeded": False},
                {**base, "quota_verified": False},
                {**base, "quota_private_proof": None},
                {**base, "quota_private_proof": {}},
                {**base, "descendant_cleanup_evidence": None},
                {**base, "descendant_cleanup_evidence": {
                    "verified": True, "scope_quiescent": False,
                    "cgroup_unpopulated": True,
                    "active_state": "active", "sub_state": "running"}},
                {**base, "descendant_cleanup_evidence": {
                    "verified": True, "scope_quiescent": True,
                    "cgroup_unpopulated": False,
                    "active_state": "inactive", "sub_state": "dead"}},
        ):
            with self.subTest(modified=modified):
                candidate = dict(self.report)
                if modified is None:
                    candidate.pop("descendant_lifecycle")
                else:
                    candidate["descendant_lifecycle"] = modified
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=candidate)
                self.assertFalse(self.dest.exists())

    def test_refuses_missing_scoped_seccomp_probe_as_controlled_error(self):
        report = {**self.report, "ghidra": {
            **self.report["ghidra"],
            "arch_scoped_seccomp_probe": None}}
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write(report=report)
        self.assertFalse(self.dest.exists())

    def test_refuses_cleanup_receipt_from_other_scope(self):
        wrong = "negresco-pe-ffffffffffffffffffffffff.scope"
        for section in ("descendant_lifecycle", "arch_scoped_seccomp_probe",
                        "arch_real_ghidra_with_both"):
            with self.subTest(section=section):
                report = {**self.report, "ghidra": dict(self.report["ghidra"])}
                if section == "descendant_lifecycle":
                    entry = dict(report[section])
                    entry["descendant_cleanup_evidence"] = {
                        **entry["descendant_cleanup_evidence"], "scope": wrong}
                    report[section] = entry
                else:
                    entry = dict(report["ghidra"][section])
                    entry["scope_cleanup_evidence"] = {
                        **entry["scope_cleanup_evidence"], "scope": wrong}
                    report["ghidra"][section] = entry
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_refuses_initial_cgroup_lifecycle_missing_or_unproven(self):
        source = self.report["cgroup_lifecycle"]
        for modification in (
                None, {"status": "PASS_NATIVE_ARCH_CGROUP"},
                {**source, "quota_private_proof": {}},
                {**source, "scope_cleanup_evidence": {}},
                {**source, "scope_cleanup_evidence": {
                    **source["scope_cleanup_evidence"],
                    "cgroup_unpopulated": False}},
                {**source, "scope": self.report["descendant_lifecycle"]["scope"]},
                {**source, "memory_max": 8 * 1024 ** 3},
                {**source, "ghidra_executed": True},
        ):
            with self.subTest(modification=modification):
                report = copy.deepcopy(self.report)
                if modification is None:
                    report.pop("cgroup_lifecycle")
                else:
                    report["cgroup_lifecycle"] = modification
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_initial_private_proof_must_match_numeric_summary(self):
        for key, value in (
                ("memory_max_bytes", 2147483648),
                ("tasks_max", 32),
                ("cpu_period", 50000),
                ("cpu_quota", 100000)):
            with self.subTest(key=key):
                report = copy.deepcopy(self.report)
                report["cgroup_lifecycle"]["quota_private_proof"][key] = value
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_s1_31_report_rejects_physically_impossible_cpu_max_values(self):
        for location in (
                ("cgroup",),
                ("cgroup_lifecycle", "quota_private_proof"),
                ("descendant_lifecycle", "quota_private_proof"),
                ("ghidra", "arch_scoped_seccomp_probe", "cgroup_verification"),
                ("ghidra", "arch_real_ghidra_with_both",
                 "quotas_verified_before_bwrap"),
                ("ghidra",)):
            for key, value in (("cpu_quota", 999),
                               ("cpu_period", 999),
                               ("cpu_period", 1000001),
                               ("cpu_period", 10 ** 12)):
                with self.subTest(location=location, key=key, value=value):
                    report = copy.deepcopy(self.report)
                    node = report
                    for part in location:
                        node = node[part]
                    node[key] = value
                    with self.assertRaises(evidence.AcceptanceReceiptError):
                        self.write(report=report)
                    self.assertFalse(self.dest.exists())

    def test_refuses_unbounded_or_forged_kernel_quota_values(self):
        paths = (
            ("cgroup",),
            ("descendant_lifecycle", "quota_private_proof"),
            ("ghidra", "arch_scoped_seccomp_probe", "cgroup_verification"),
            ("ghidra", "arch_real_ghidra_with_both",
             "quotas_verified_before_bwrap"),
        )
        for path in paths:
            for field, value in (
                    (("memory_max_bytes" if len(path) > 1 else "memory_max"),
                     8 * 1024 ** 3),
                    (("tasks_max" if len(path) > 1 else "pids_max"), True),
                    ("cpu_period", "max"),
                    ("cpu_quota", 300000), ("cpu_quota", 0)):
                with self.subTest(path=path, field=field, value=value):
                    report = copy.deepcopy(self.report)
                    quotas = report
                    for part in path:
                        quotas = quotas[part]
                    quotas[field] = value
                    with self.assertRaises(evidence.AcceptanceReceiptError):
                        self.write(report=report)
                    self.assertFalse(self.dest.exists())

    def test_refuses_replayed_scope_identity_across_stages(self):
        for path in (
                ("descendant_lifecycle",),
                ("ghidra", "arch_scoped_seccomp_probe"),
                ("ghidra", "arch_real_ghidra_with_both")):
            with self.subTest(path=path):
                report = copy.deepcopy(self.report)
                entry = report
                for part in path:
                    entry = entry[part]
                other_scope = (
                    self.report["ghidra"]["arch_scoped_seccomp_probe"]["scope"]
                    if len(path) == 1 else
                    self.report["descendant_lifecycle"]["scope"])
                entry["scope"] = other_scope
                cleanup_key = ("descendant_cleanup_evidence" if len(path) == 1
                               else "scope_cleanup_evidence")
                entry[cleanup_key]["scope"] = other_scope
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_refuses_jvm_kernel_counter_provenance_inconsistencies(self):
        for field, value in (
                ("measurement_source", "user-supplied"),
                ("additional_filters_observed", 0),
                ("additional_filters_observed", True),
                ("filters_before_bwrap", -1),
                ("filters_in_ghidra", 5000),
                ("seccomp_mode", True)):
            with self.subTest(field=field, value=value):
                report = copy.deepcopy(self.report)
                report["ghidra"]["arch_real_ghidra_with_both"][
                    "ghidra_jvm_seccomp_evidence"][field] = value
                with self.assertRaises(evidence.AcceptanceReceiptError):
                    self.write(report=report)
                self.assertFalse(self.dest.exists())

    def test_fails_before_writing_if_source_changed_to_directory(self):
        self.source.unlink()
        self.source.mkdir()
        with self.assertRaises(evidence.AcceptanceReceiptError):
            self.write()
        self.assertFalse(self.dest.exists())


if __name__ == "__main__":
    unittest.main()
