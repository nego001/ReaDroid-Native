"""Contract test for synthetic, non-private capacity metrics extraction."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "tools/extract_m2_capacity_logcat.py"
spec = importlib.util.spec_from_file_location("m2_capacity_extractor", PARSER)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


def payload(api=29):
    result = {"fixture": {"synthetic": True, "contentBytes": 10240011,
                          "archiveBytes": 10244000, "fileCount": 2502,
                          "entryCount": 2503, "deviceApi": api},
              "result": "PASS"}
    for stage in extractor.EXPECTED[1:]:
        result[stage] = {"stage": stage, "wallMs": 1, "processCpuMs": 1,
                         "javaHeapUsedBytes": 1024, "nativeHeapAllocatedBytes": 5,
                         "processPssKib": 10}
    return result


class CapacityLogExtractionTests(unittest.TestCase):
    def line(self, value):
        return "10-26 04:49:01.123  1234  5678 I M2Capacity: RESULT_JSON:" + json.dumps(
            value, separators=(",", ":"))

    def test_exactly_one_complete_synthetic_result_is_accepted(self):
        result = payload()
        text = "system: unrelated line\n" + self.line(result) + "\n"
        self.assertEqual(result, extractor.parse(text, 29))

    def test_missing_duplicate_or_wrong_api_is_rejected(self):
        valid = self.line(payload())
        for text, api in ((valid + "\n" + valid, 29), ("unrelated", 29),
                          (valid, 35)):
            with self.subTest(text=text[:20], api=api):
                with self.assertRaises(ValueError):
                    extractor.parse(text, api)

    def test_unexpected_fields_or_nonsynthetic_fixture_are_rejected(self):
        for mutation in ("privatePath", "nonsynthetic", "metric"):
            value = payload()
            if mutation == "privatePath":
                value["privatePath"] = "/data/data/secret"
            elif mutation == "nonsynthetic":
                value["fixture"]["synthetic"] = False
            else:
                value["zipAdmission"]["processPssKib"] = -1
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    extractor.parse(self.line(value), 29)

    def test_truncated_log_json_is_rejected(self):
        with self.assertRaises(ValueError):
            extractor.parse("M2Capacity: RESULT_JSON:{", 29)


if __name__ == "__main__":
    unittest.main()
