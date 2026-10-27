"""Contracts for actual Ghidra + scoped-seccomp CI helper.

The native cgroup verifier is always mocked by this CI helper and the tests
must never classify that environment as homologated Arch VM.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import pe_scoped_ghidra_bridge_real_ci as ci


class RealBridgeGhidraContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ghidra = self.root / "verified-ghidra"
        self.ghidra.mkdir()
        self.archive = self.root / "synthetic-release.zip"
        self.archive.write_text("test-only", encoding="utf-8")
        self.pe = self.root / "synthetic.exe"
        self.pe.write_bytes(b"MZ mocked fixture")

    def tearDown(self):
        self.tmp.cleanup()

    def _run_mocked_contract(self, *, exit_code=0, decompiled=True,
                             release_verified=True, receipt=True,
                             inventory_count=3):
        def fake_launch(unit, argv, **kw):
            self.assertEqual(unit, ci.SCOPE_UNIT)
            self.assertTrue(kw["timeout_seconds"] >= 90)
            self.assertIn("-postScript", argv)
            self.assertIn("NegrescoDeepPreview.java", argv)
            # The mocked launcher must model its real cgroup verification;
            # only the Ubuntu end-to-end smoke executes the real launcher.
            ci.bridge.verify_cgroup_limits(
                ci.bridge.MEMORY_MAX_BYTES,
                ci.bridge.TASKS_MAX,
                ci.bridge.CPU_QUOTA_PERCENT,
                expected_scope=ci.SCOPE_UNIT)
            if receipt:
                print('{"scope_seccomp_guard":"passed",'
                      '"scope":"' + ci.SCOPE_UNIT + '",'
                      '"filters_compiled_inside_scope":true}')
            return exit_code

        with mock.patch.object(ci.os, "geteuid", return_value=1000):
            with mock.patch.object(ci, "inspect_pe",
                                   return_value={"architecture": "x86_64"}):
                with mock.patch.object(
                        ci, "verify_pinned_ghidra_tree",
                        return_value={"verified": release_verified}):
                    with mock.patch.object(
                            ci, "build_command",
                            side_effect=lambda home, work, secs, deep_preview:
                                ["/usr/bin/bwrap", "--unshare-all", "--",
                                 "/opt/negresco-ghidra/support/analyzeHeadless",
                                 "/work/project", "NegrescoAutomaticPE",
                                 "-import", "/work/input.exe",
                                 "-postScript", "NegrescoFunctionInventory.java",
                                 "/work/ghidra-functions.json",
                                 "-postScript", "NegrescoDeepPreview.java",
                                 "/work/ghidra-deep.json"]):
                        with mock.patch.object(
                                ci.bridge, "launch_scoped_bwrap",
                                side_effect=fake_launch) as launch:
                            with mock.patch.object(
                                    ci, "_validated_function_evidence",
                                    return_value={
                                        "total_discovered": inventory_count}) as inv:
                                with mock.patch.object(
                                        ci, "_validated_deep_evidence",
                                        return_value={"functions": [
                                            {"decompile_status": "ok" if decompiled
                                             else "error"}]}) as deep:
                                    if (exit_code == 0 and decompiled
                                            and release_verified and receipt
                                            and inventory_count > 0):
                                        result = ci.run_real_bridge_ghidra(
                                            self.ghidra, self.archive, self.pe)
                                        self.assertEqual(result["decompiled_functions"], 1)
                                        self.assertEqual(
                                            result["cgroup_verification"],
                                            "MOCK_ONLY_NOT_HOMOLOGATED")
                                        self.assertFalse(result["native_arch_vm_executed"])
                                        launch.assert_called_once()
                                        inv.assert_called_once()
                                        deep.assert_called_once()
                                    else:
                                        with self.assertRaises(ci.RealBridgeGhidraError):
                                            ci.run_real_bridge_ghidra(
                                                self.ghidra, self.archive, self.pe)
                                        if not release_verified:
                                            launch.assert_not_called()

    def test_mocked_receipts_do_not_claim_real_cgroup(self):
        self._run_mocked_contract()

    def test_fail_closed_if_pinned_release_is_not_verified(self):
        self._run_mocked_contract(release_verified=False)

    def test_fail_closed_if_child_fails_or_receipt_is_absent(self):
        self._run_mocked_contract(exit_code=13)
        self._run_mocked_contract(receipt=False)

    def test_fail_closed_on_empty_inventory_or_missing_decompilation(self):
        self._run_mocked_contract(inventory_count=0)
        self._run_mocked_contract(decompiled=False)

    def test_rejects_wrong_architecture_before_ghidra(self):
        with mock.patch.object(ci.os, "geteuid", return_value=1000):
            with mock.patch.object(ci, "inspect_pe",
                                   return_value={"architecture": "arm64"}):
                with mock.patch.object(ci.bridge, "launch_scoped_bwrap") as launch:
                    with self.assertRaisesRegex(
                            ci.RealBridgeGhidraError, "x86_64"):
                        ci.run_real_bridge_ghidra(self.ghidra, self.archive, self.pe)
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
