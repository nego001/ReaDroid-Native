"""PE-S2.09: journald policy is a mocked DECLARED config check, not a VM."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest import mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_journald_policy as jp

VALID = """# merged systemd-analyze cat-config --tldr output
[Journal]
Storage=volatile
RuntimeMaxUse=32M
RuntimeMaxFileSize=8M
RuntimeKeepFree=64M
RateLimitIntervalSec=30s
RateLimitBurst=500
ForwardToSyslog=no
ForwardToKMsg=no
ForwardToConsole=no
ForwardToWall=no
"""


class DeclaredJournaldPolicyTests(unittest.TestCase):
    def test_bounded_volatility_is_only_local_declaration(self):
        result = jp.parse_declared_journald_config(VALID)
        self.assertEqual(result["runtime_max_use_bytes"], 32 * 1024**2)
        self.assertEqual(result["rate_limit_interval_seconds"], 30)
        self.assertFalse(result["journal_kernel_quota_verified"])
        self.assertFalse(result["journal_daemon_effective_runtime_verified"])
        self.assertFalse(result["independent_vm_attested"])
        self.assertFalse(result["release_authorized"])

    def test_last_value_wins_for_merged_dropin(self):
        result = jp.parse_declared_journald_config(
            VALID.replace("RuntimeMaxUse=32M",
                          "RuntimeMaxUse=2G\n[Journal]\nRuntimeMaxUse=16M"))
        self.assertEqual(result["runtime_max_use_bytes"], 16 * 1024**2)

    def test_missing_or_nonvolatile_storage_refused(self):
        for bad in ("Storage=persistent", "Storage=auto", "Storage=none",
                    "Storage="):
            with self.subTest(bad=bad), self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(
                    VALID.replace("Storage=volatile", bad))

    def test_default_and_unlimited_disk_settings_refused(self):
        for bad in ("RuntimeMaxUse=0", "RuntimeMaxUse=2G",
                    "RuntimeMaxUse=infinity", "RuntimeMaxUse=50%",
                    "RuntimeMaxUse=32.5M", "RuntimeMaxUse=32MB"):
            with self.subTest(bad=bad), self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(
                    VALID.replace("RuntimeMaxUse=32M", bad))

    def test_file_and_keepfree_limits_refused(self):
        for before, after in (
            ("RuntimeMaxFileSize=8M", "RuntimeMaxFileSize=64M"),
            ("RuntimeMaxFileSize=8M", "RuntimeMaxFileSize=0"),
            ("RuntimeKeepFree=64M", "RuntimeKeepFree=1M"),
            ("RuntimeKeepFree=64M", "RuntimeKeepFree=auto")):
            with self.subTest(after=after), self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(VALID.replace(before, after))

    def test_rate_limit_cannot_be_disabled_or_excessive(self):
        for before, after in (
            ("RateLimitIntervalSec=30s", "RateLimitIntervalSec=0"),
            ("RateLimitIntervalSec=30s", "RateLimitIntervalSec=2min"),
            ("RateLimitBurst=500", "RateLimitBurst=0"),
            ("RateLimitBurst=500", "RateLimitBurst=2000")):
            with self.subTest(after=after), self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(VALID.replace(before, after))

    def test_forwarding_and_missing_settings_refused(self):
        for key in ("ForwardToSyslog", "ForwardToKMsg", "ForwardToConsole",
                    "ForwardToWall"):
            with self.subTest(key=key), self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(
                    VALID.replace(key+"=no", key+"=yes"))
        with self.assertRaises(jp.JournaldPolicyError):
            jp.parse_declared_journald_config(
                VALID.replace("RuntimeKeepFree=64M\n", ""))

    def test_wrong_section_does_not_count(self):
        with self.assertRaises(jp.JournaldPolicyError):
            jp.parse_declared_journald_config(
                VALID.replace("[Journal]", "[Other]"))

    def test_truncated_binary_and_oversized_input_refused(self):
        for bad in ("", VALID+"\x00", VALID+"\r", VALID*600):
            with self.subTest(length=len(bad)), self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(bad)

    def test_unsafe_line_and_continuation_refused(self):
        for bad in (VALID+"[Journal]\nRuntimeMaxUse=8M\\\n",
                    VALID+"[Journal]\n!RuntimeMaxUse=8M\n",
                    VALID+"[Journal]\nBrokenSetting\n"):
            with self.assertRaises(jp.JournaldPolicyError):
                jp.parse_declared_journald_config(bad)

    def test_root_is_rejected_before_subprocess(self):
        with (mock.patch.object(jp.os, "geteuid", return_value=0),
              mock.patch.object(jp.subprocess, "run") as run):
            with self.assertRaises(jp.JournaldPolicyError):
                jp.require_journald_declared_policy()
            run.assert_not_called()

    def test_untrusted_binary_is_rejected_before_subprocess(self):
        fake = SimpleNamespace(st_mode=0o100777, st_uid=1000)
        with (mock.patch.object(jp.os, "geteuid", return_value=1000),
              mock.patch.object(jp.SYSTEMD_ANALYZE.__class__, "lstat",
                                return_value=fake),
              mock.patch.object(jp.subprocess, "run") as run):
            with self.assertRaises(jp.JournaldPolicyError):
                jp.require_journald_declared_policy()
            run.assert_not_called()

    def test_readonly_command_does_not_modify_host(self):
        fake = SimpleNamespace(st_mode=0o100755, st_uid=0)
        process = SimpleNamespace(returncode=0, stdout=VALID.encode(), stderr=b"")
        with (mock.patch.object(jp.os, "geteuid", return_value=1000),
              mock.patch.object(jp.SYSTEMD_ANALYZE.__class__, "lstat",
                                return_value=fake),
              mock.patch.object(jp.os, "access", return_value=True),
              mock.patch.object(jp.subprocess, "run", return_value=process) as run):
            result = jp.require_journald_declared_policy()
        self.assertFalse(result["journal_kernel_quota_verified"])
        argv = run.call_args.args[0]
        self.assertEqual(argv, ["/usr/bin/systemd-analyze", "cat-config",
                                "--tldr", "systemd/journald.conf"])
        self.assertFalse(run.call_args.kwargs["check"])

    def test_timeout_or_empty_config_refuses(self):
        fake = SimpleNamespace(st_mode=0o100755, st_uid=0)
        with (mock.patch.object(jp.os, "geteuid", return_value=1000),
              mock.patch.object(jp.SYSTEMD_ANALYZE.__class__, "lstat",
                                return_value=fake),
              mock.patch.object(jp.os, "access", return_value=True),
              mock.patch.object(jp.subprocess, "run",
                                return_value=SimpleNamespace(
                                    returncode=0, stdout=b"", stderr=b""))):
            with self.assertRaises(jp.JournaldPolicyError):
                jp.require_journald_declared_policy()


if __name__ == "__main__":
    unittest.main()
