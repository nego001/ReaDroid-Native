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
                "vm_confirmed": True, "container": False},
            "descendants_terminated": True,
            "cgroup": {"memory_max": 4294967296, "pids_max": 128,
                       "cpu_quota": 200000, "cpu_period": 100000},
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
                    "active_state": "inactive", "sub_state": "dead"}},
            "windows_binary_executed": False,
            "ghidra": {
                "ghidra_integrity": {"verified": True},
                "arch_scoped_seccomp_probe": {
                    "status": "PASS_NATIVE_ARCH_VM_SCOPED_SECCOMP",
                    "scope": "negresco-pe-aaaaaaaaaaaaaaaaaaaaaaaa.scope",
                    "cgroup_verification": {
                        "verification": "guard_verified_before_bwrap",
                        "memory_max_bytes": 4294967296,
                        "tasks_max": 128, "cpu_quota": 200000,
                        "cpu_period": 100000},
                    "scope_cleanup_evidence": {
                        "scope": "negresco-pe-aaaaaaaaaaaaaaaaaaaaaaaa.scope",
                        "verified": True, "scope_quiescent": True,
                        "cgroup_unpopulated": True}},
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
