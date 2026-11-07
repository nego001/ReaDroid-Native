"""Synthetic-only S2.13 runtime and cleanup text integrity tests."""
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pe_arch_vm_s2_13_runtime_log_chain as chain

COMMIT = "a"*40
CHALLENGE = "b"*64
DOMAIN = "reviewer-native-arch-01"
UUID = "12345678-abcd-4ef0-8123-123456789abc"
HOST = "c"*64
GUEST = "d"*64
SESSION = "1"*64


def make_fixture(*, commit=COMMIT, challenge=CHALLENGE,
                 domain=DOMAIN, uuid=UUID, host=HOST, guest=GUEST,
                 session=SESSION):
    common = {
        "classification": chain.CLASSIFICATION, "source_commit": commit,
        "reviewer_challenge": challenge, "domain_name": domain,
        "domain_uuid": uuid, "prior_host_record_sha256": host,
        "prior_guest_record_sha256": guest, "session_id": session,
        "scope": "negresco-pe-"+"2"*24+".scope",
        "windows_binary_executed": "false",
        "independent_vm_attestation": "false", "release_authorized": "false"}
    def emit(data):
        return "".join(f"{k}={v}\n" for k,v in sorted(data.items())).encode("ascii")
    runtime = emit({**common, "schema": chain.RUNTIME_SCHEMA,
                    "memory_max_bytes": str(4*1024**3), "pids_max": "128",
                    "cpu_quota_us": "200000", "cpu_period_us": "100000",
                    "seccomp_mode": "2", "seccomp_filter_count": "2"})
    cleanup = emit({**common, "schema": chain.CLEANUP_SCHEMA,
                    "prior_runtime_record_sha256": hashlib.sha256(runtime).hexdigest(),
                    "load_state": "not-found", "active_state": "inactive",
                    "sub_state": "dead", "cgroup_populated": "0",
                    "stop_request_accepted": "true"})
    return runtime, cleanup


def review(r,c,**kw):
    opts = {"expected_source_commit": COMMIT, "expected_challenge": CHALLENGE,
            "expected_domain": DOMAIN, "expected_domain_uuid": UUID,
            "expected_host_sha256": HOST, "expected_guest_sha256": GUEST,
            "expected_session_id": SESSION}
    return chain.review_runtime_cleanup_text(r,c,**{**opts,**kw})


def repin(r,c,old,new):
    different = r.replace(old,new)
    linked = c.replace(hashlib.sha256(r).hexdigest().encode(),
                       hashlib.sha256(different).hexdigest().encode())
    return different,linked


class RuntimeTextChainContracts(unittest.TestCase):
    def setUp(self):
        self.r,self.c = make_fixture()

    def test_valid_synthetic_claim_remains_hold(self):
        result=review(self.r,self.c)
        self.assertEqual(result["records_structurally_checked"],2)
        self.assertFalse(result["independent_vm_attestation"])

    def test_signed_generic_log_can_never_pass_semantic_gate(self):
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(b"PASS\n",b"cleanup successful\n")

    def test_hash_chain_detects_replay(self):
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(self.r.replace(b"seccomp_filter_count=2",
                                  b"seccomp_filter_count=3"),self.c)

    def test_mismatched_session_or_scope(self):
        for c in (self.c.replace(b"session_id="+b"1"*64,b"session_id="+b"8"*64),
                  self.c.replace(b"negresco-pe-"+b"2"*24,
                                 b"negresco-pe-"+b"3"*24)):
            with self.assertRaises(chain.RuntimeTextReviewError):
                review(self.r,c)

    def test_rehashed_unbounded_cgroup_rejected(self):
        r,c=repin(self.r,self.c,b"pids_max=128",b"pids_max=999999")
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(r,c)

    def test_rehashed_invalid_seccomp_rejected(self):
        r,c=repin(self.r,self.c,b"seccomp_mode=2",b"seccomp_mode=0")
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(r,c)

    def test_false_cleanup_rejected(self):
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(self.r,self.c.replace(b"cgroup_populated=0",b"cgroup_populated=1"))

    def test_wrong_pinned_guest_or_commit_rejected(self):
        for opts in ({"expected_guest_sha256":"f"*64},
                     {"expected_source_commit":"e"*40}):
            with self.assertRaises(chain.RuntimeTextReviewError):
                review(self.r,self.c,**opts)

    def test_wrong_out_of_band_session_pin_rejected(self):
        for bad in ("f"*64, "0"*64, "F"*64, "", "1"*63):
            with self.subTest(bad=bad), self.assertRaises(
                    chain.RuntimeTextReviewError):
                review(self.r, self.c, expected_session_id=bad)

    def test_rehashed_both_logs_from_other_session_rejected(self):
        # Even two rewritten, rehashed, newly signed logs cannot override
        # a separately selected session pin.
        old_session = b"session_id=" + SESSION.encode("ascii")
        new_session = b"session_id=" + b"f"*64
        runtime = self.r.replace(old_session, new_session)
        cleanup = self.c.replace(old_session, new_session)
        cleanup = cleanup.replace(
            hashlib.sha256(self.r).hexdigest().encode("ascii"),
            hashlib.sha256(runtime).hexdigest().encode("ascii"))
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(runtime, cleanup)

    def test_no_forged_release_or_pe_execution(self):
        r,c=repin(self.r,self.c,
                  b"release_authorized=false",b"release_authorized=true")
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(r,c)
        with self.assertRaises(chain.RuntimeTextReviewError):
            review(self.r,self.c.replace(
                b"windows_binary_executed=false",
                b"windows_binary_executed=true"))

    def test_malformed_duplicate_unknown_and_binary_records(self):
        bad=(self.r+b"scope=other.scope\n",
             self.r.replace(b"pids_max=128\n",b""),
             self.r.replace(b"scope=",b"unknown=x\nscope="),
             self.r.replace(b"scope=",b"scope\x00="),
             self.r[:-1],self.r.replace(b"pids_max=128",b"pids_max=12\r8"))
        for r in bad:
            with self.subTest(sample=r[:30]),self.assertRaises(chain.RuntimeTextReviewError):
                review(r,self.c)


if __name__=="__main__":
    unittest.main()
