"""Standalone tests for the strict M2.6 emulator evidence parser."""
import importlib.util
import json
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / "tools/extract_m2_fingerprint_logcat.py"
spec = importlib.util.spec_from_file_location("m26parser", SRC)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def valid(api=29):
    samples = []
    for phase, kind in parser.PHASES:
        samples.append({"phase": phase, "kind": kind, "paths": 8192,
                        "wallMs": 200, "processCpuMs": 195,
                        "heapBeforeBytes": 1000000,
                        "heapRetainedBytes": 1450000,
                        "heapDeltaBytes": 450000, "processPssKib": 30000})
    return {"schema": "m2_path_fingerprint_abba_v1", "synthetic": True,
            "deviceApi": api, "pathsPerSample": 8192,
            "pathPrefixChars": 770, "samples": samples, "result": "PASS"}


def line(obj):
    return "10-26 05:02:11.123 123 456 I M2Fingerprint: RESULT_JSON:" + json.dumps(obj)


class M26EvidenceTests(unittest.TestCase):
    def test_one_complete_abba_is_accepted(self):
        expected = valid()
        self.assertEqual(parser.parse("unrelated line\n" + line(expected), 29), expected)

    def test_wrong_api_missing_or_duplicate_report_are_rejected(self):
        payload = line(valid())
        for text, api in (("unrelated", 29), (payload + "\n" + payload, 29),
                          (payload, 35), ("M2Fingerprint RESULT_JSON:{", 29)):
            with self.subTest(case=text[:30], api=api):
                with self.assertRaises(ValueError):
                    parser.parse(text, api)

    def test_extra_private_fields_wrong_order_and_metric_mismatch_rejected(self):
        for mode in ("private", "order", "delta", "type", "nonsynthetic"):
            data = valid()
            if mode == "private":
                data["samples"][0]["rawPath"] = "/data/local/secret"
            elif mode == "order":
                data["samples"][0]["phase"] = "B1"
            elif mode == "delta":
                data["samples"][2]["heapDeltaBytes"] += 1
            elif mode == "type":
                data["samples"][3]["wallMs"] = False
            else:
                data["synthetic"] = False
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    parser.parse(line(data), 29)


if __name__ == "__main__":
    unittest.main()
