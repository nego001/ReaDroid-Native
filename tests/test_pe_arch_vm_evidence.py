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
        source = mock.patch.object(evidence, "SOURCE_FILES",
                                   ("tools/synthetic.py",))
        source.start()
        self.addCleanup(source.stop)
        self.report = {
            "status": "PASS_PE_S1_5_ARCH_VM",
            "environment": {
                "status": "ARCH_VM_PREFLIGHT_PASSED",
                "vm_confirmed": True, "container": False,
                "root": False, "systemd_user_bus": True},
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
                    "cgroup_unpopulated": True,
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
                    "cgroup_unpopulated": True,
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
                        "cgroup_unpopulated": True,
                        "active_state": "inactive", "sub_state": "dead"}},
                "arch_real_ghidra_with_both": {
                    "status": "PASS_NATIVE_ARCH_REAL_GHIDRA_WITH_CGROUP_AND_SECCOMP",
                    "scope": "negresco-pe-bbbbbbbbbbbbbbbbbbbbbbbb.scope",
                    "scope_cleanup_verified": True,
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
            self.dest if path is None else path, source_root=self.root)

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

    def test_private_receipt_records_source_hashes_without_claiming_signature(self):
        written = self.write()
        self.assertEqual(written["path"], str(self.dest))
        saved = self.dest.read_bytes()
        self.assertEqual(written["receipt_sha256"],
                         hashlib.sha256(saved).hexdigest())
        payload = json.loads(saved)
        self.assertEqual(payload["schema"],
                         "negresco_native_arch_vm_local_receipt_v1")
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
        result = review.verify_local_receipt(self.dest, self.root)
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
            review.verify_local_receipt(self.dest, self.root)
        self.source.unlink()
        unrelated = self.root / "unrelated.txt"
        unrelated.write_text("print('harmless fixture')\n", encoding="utf-8")
        self.source.symlink_to(unrelated)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root)

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
                    review.verify_local_receipt(self.dest, self.root)
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
                review.verify_local_receipt(self.dest, self.root)

    def test_offline_audit_refuses_untrusted_private_paths(self):
        self.write()
        alias = self.root / "linked-proof"
        alias.symlink_to(self.private, target_is_directory=True)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(alias / self.dest.name, self.root)
        self.private.chmod(0o755)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root)
        self.private.chmod(0o700)
        self.dest.chmod(0o644)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, self.root)

    def test_offline_review_and_writer_refuse_symlinked_receipt_ancestor(self):
        self.write()
        outer = self.root / "actual-parent"
        outer.mkdir(mode=0o700)
        nested = outer / "private"
        nested.mkdir(mode=0o700)
        copied = nested / "copied.json"
        copied.write_bytes(self.dest.read_bytes())
        copied.chmod(0o600)
        self.assertEqual(review.verify_local_receipt(copied, self.root)["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        alias = self.root / "linked-ancestor"
        alias.symlink_to(outer, target_is_directory=True)
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(alias / "private" / "copied.json",
                                        self.root)
        bad_dest = alias / "private" / "new.json"
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.write_receipt_no_overwrite(
                self.report, bad_dest, source_root=self.root)
        self.assertFalse((nested / "new.json").exists())

    def test_offline_review_and_writer_refuse_source_root_ancestor_symlink(self):
        self.write()
        outer = self.root / "actual-sources"
        checkout = outer / "checkout"
        (checkout / "tools").mkdir(parents=True, mode=0o700)
        (checkout / "tools" / "synthetic.py").write_bytes(self.source.read_bytes())
        self.assertEqual(review.verify_local_receipt(self.dest, checkout)["status"],
                         "LOCAL_RECEIPT_CONSISTENCY_VALIDATED")
        alias = self.root / "linked-sources"
        alias.symlink_to(outer, target_is_directory=True)
        bad_root = alias / "checkout"
        with self.assertRaises(review.ReceiptReviewError):
            review.verify_local_receipt(self.dest, bad_root)
        bad_dest = self.private / "another.json"
        with self.assertRaises(evidence.AcceptanceReceiptError):
            evidence.write_receipt_no_overwrite(
                self.report, bad_dest, source_root=bad_root)
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
            review.verify_local_receipt(self.dest, self.root)

    def test_offline_reviewer_cli_uses_precise_non_attestation_status(self):
        self.write()
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        stdout = StringIO()
        with redirect_stdout(stdout):
            success = review.main([
                "--receipt", str(self.dest),
                "--source-root", str(self.root)])
        self.assertEqual(success, 0)
        self.assertFalse(json.loads(stdout.getvalue())[
            "native_kernel_execution_independently_verified"])
        stderr = StringIO()
        with redirect_stderr(stderr):
            failure = review.main([
                "--receipt", str(self.root / "missing.json"),
                "--source-root", str(self.root)])
        self.assertEqual(failure, 2)
        self.assertEqual(json.loads(stderr.getvalue())["status"],
                         "REJECTED_LOCAL_RECEIPT")

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
