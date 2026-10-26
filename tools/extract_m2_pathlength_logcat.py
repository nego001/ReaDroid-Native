#!/usr/bin/env python3
"""Whitelist only three M2.8 synthetic, paired Android path-length profiles.

No raw logcat or APK filenames are persisted as CI artifacts. Require short,
medium and long cohorts and four exactly ordered ABBA samples per cohort.
"""
import json
import pathlib
import sys

TAG = "M2PathLength"
PREFIX = "RESULT_JSON:"
PATH_LENGTHS = (32, 128, 768)
FIELDS = {"schema", "synthetic", "deviceApi", "pathChars",
          "pathsPerSample", "samples", "result"}
SAMPLE_FIELDS = {"phase", "kind", "paths", "cpuMs", "wallMs",
                 "heapDeltaBytes", "pssKib"}
ORDER = (("A1", "stringSet"), ("B1", "fingerprint128"),
         ("B2", "fingerprint128"), ("A2", "stringSet"))


def parse(source: str, api: int) -> dict:
    profiles = {}
    for line in source.splitlines():
        if TAG not in line or PREFIX not in line:
            continue
        try:
            data = json.loads(line.split(PREFIX, 1)[1].strip())
        except json.JSONDecodeError as error:
            raise ValueError("M2.8: JSON truncado ou inválido") from error
        if not isinstance(data, dict) or set(data) != FIELDS:
            raise ValueError("M2.8: campos extras ou ausentes")
        if (data["schema"] != "m2_path_length_abba_v1"
                or data["synthetic"] is not True
                or data["result"] != "PASS"
                or type(data["deviceApi"]) is not int or data["deviceApi"] != api
                or type(data["pathChars"]) is not int
                or data["pathChars"] not in PATH_LENGTHS
                or type(data["pathsPerSample"]) is not int
                or data["pathsPerSample"] != 4096):
            raise ValueError("M2.8: esquema, corpus ou API não autorizado")
        length = data["pathChars"]
        if length in profiles:
            raise ValueError("M2.8: perfil duplicado")
        pairs = data["samples"]
        if not isinstance(pairs, list) or len(pairs) != 4:
            raise ValueError("M2.8: comparação ABBA incompleta")
        for sample, (phase, kind) in zip(pairs, ORDER):
            if not isinstance(sample, dict) or set(sample) != SAMPLE_FIELDS:
                raise ValueError("M2.8: amostra com campos inesperados")
            if sample["phase"] != phase or sample["kind"] != kind:
                raise ValueError("M2.8: ordem ABBA incorreta")
            if type(sample["paths"]) is not int or sample["paths"] != 4096:
                raise ValueError("M2.8: contagem incorreta")
            for field in ("cpuMs", "wallMs", "heapDeltaBytes", "pssKib"):
                value = sample[field]
                if type(value) is not int:
                    raise ValueError("M2.8: medição inválida")
                if field != "heapDeltaBytes" and value < 0:
                    raise ValueError("M2.8: medição negativa")
        profiles[length] = data
    if set(profiles) != set(PATH_LENGTHS):
        raise ValueError("M2.8: deve fornecer os três perfis exatamente uma vez")
    return {"schema": "m2_path_length_collection_v1", "synthetic": True,
            "deviceApi": api, "profiles": [profiles[length] for length in PATH_LENGTHS]}


def main() -> int:
    if len(sys.argv) != 4:
        print("Uso: extract_m2_pathlength_logcat.py logcat.txt output.json API",
              file=sys.stderr)
        return 2
    source, dest, api = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), int(sys.argv[3])
    result = parse(source.read_text(encoding="utf-8", errors="replace"), api)
    dest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"M2.8 API{api}: 3 perfis, 4 medições ABBA por perfil validadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
