"""Negative and positive cases for M2.8 synthetic per-length telemetry."""
import importlib.util
import json
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / "tools/extract_m2_pathlength_logcat.py"
spec = importlib.util.spec_from_file_location("m28pathlength", SRC)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def profile(length, api=29):
    return {
        "schema": "m2_path_length_abba_v1",
        "synthetic": True, "deviceApi": api,
        "pathChars": length, "pathsPerSample": 4096, "result": "PASS",
        "samples": [
            {"phase": phase, "kind": kind, "paths": 4096,
             "cpuMs": 9, "wallMs": 11, "heapDeltaBytes": 2048, "pssKib": 1024}
            for phase, kind in parser.ORDER
        ],
    }


def lines(profiles):
    return "\n".join("10-26 05:00:00.000 I M2PathLength: RESULT_JSON:"
                     + json.dumps(obj) for obj in profiles)


class M28EvidenceTests(unittest.TestCase):
    def test_exact_three_profiles_and_order_accepted(self):
        result = parser.parse(lines([profile(x) for x in parser.PATH_LENGTHS]), 29)
        self.assertEqual([32, 128, 768], [x["pathChars"] for x in result["profiles"]])
        self.assertEqual("m2_path_length_collection_v1", result["schema"])

    def test_missing_duplicate_wrong_api_and_truncated_rejected(self):
        good = [profile(x) for x in parser.PATH_LENGTHS]
        cases = [
            (lines(good[:2]), 29),
            (lines(good + [profile(32)]), 29),
            (lines(good), 35),
            (lines(good) + "\nM2PathLength: RESULT_JSON:{", 29),
        ]
        for text, api in cases:
            with self.subTest(case=text[-45:], api=api):
                with self.assertRaises(ValueError):
                    parser.parse(text, api)

    def test_non_synthetic_raw_fields_invalid_count_or_order_rejected(self):
        for scenario in ("private", "nonsynthetic", "bad_count", "bad_order", "bad_type"):
            docs = [profile(x) for x in parser.PATH_LENGTHS]
            if scenario == "private":
                docs[0]["paths"] = ["/data/private/confidential.apk"]
            elif scenario == "nonsynthetic":
                docs[1]["synthetic"] = False
            elif scenario == "bad_count":
                docs[2]["samples"][0]["paths"] = 4095
            elif scenario == "bad_order":
                docs[0]["samples"][1]["phase"] = "A1"
            else:
                docs[1]["samples"][2]["cpuMs"] = True
            with self.subTest(scenario=scenario):
                with self.assertRaises(ValueError):
                    parser.parse(lines(docs), 29)


if __name__ == "__main__":
    unittest.main()
