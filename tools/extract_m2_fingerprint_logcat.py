#!/usr/bin/env python3
"""Extract only the synthetic M2.6 paired path benchmark, never raw APK data."""
import json
import pathlib
import sys

TAG = "M2Fingerprint"
PREFIX = "RESULT_JSON:"
FIELDS = {"schema", "synthetic", "deviceApi", "pathsPerSample",
          "pathPrefixChars", "samples", "result"}
SAMPLE_FIELDS = {"phase", "kind", "paths", "wallMs", "processCpuMs",
                 "heapBeforeBytes", "heapRetainedBytes", "heapDeltaBytes",
                 "processPssKib"}
PHASES = (("A1", "stringSet"), ("B1", "fingerprint128"),
          ("B2", "fingerprint128"), ("A2", "stringSet"))


def parse(content: str, api: int) -> dict:
    found = []
    for line in content.splitlines():
        if TAG not in line or PREFIX not in line:
            continue
        try:
            obj = json.loads(line.split(PREFIX, 1)[1].strip())
        except json.JSONDecodeError as error:
            raise ValueError("M2.6 recebeu JSON incompleto") from error
        if not isinstance(obj, dict) or set(obj) != FIELDS:
            raise ValueError("Campos indevidos ou ausentes no relatório M2.6")
        if (obj["schema"] != "m2_path_fingerprint_abba_v1"
                or obj["synthetic"] is not True or obj["result"] != "PASS"
                or obj["deviceApi"] != api or obj["pathsPerSample"] != 8192
                or not isinstance(obj["pathPrefixChars"], int)
                or obj["pathPrefixChars"] < 700
                or obj["pathPrefixChars"] > 1024):
            raise ValueError("Esquema, API ou amostra M2.6 incompatível")
        samples = obj["samples"]
        if not isinstance(samples, list) or len(samples) != 4:
            raise ValueError("M2.6 deve fornecer os quatro pares ABBA")
        for value, (phase, kind) in zip(samples, PHASES):
            if not isinstance(value, dict) or set(value) != SAMPLE_FIELDS:
                raise ValueError("Campos de amostra não autorizados")
            if value.get("phase") != phase or value.get("kind") != kind:
                raise ValueError("Amostras ABBA fora da ordem autorizada")
            if value.get("paths") != 8192:
                raise ValueError("Quantidade de caminhos não confere")
            for key in SAMPLE_FIELDS - {"phase", "kind"}:
                if key == "paths":
                    continue
                number = value.get(key)
                if (isinstance(number, bool) or not isinstance(number, int)
                        or (key != "heapDeltaBytes" and number < 0)):
                    raise ValueError("Amostra numérica inválida: " + key)
            if (value["heapRetainedBytes"] - value["heapBeforeBytes"]
                    != value["heapDeltaBytes"]):
                raise ValueError("Diferença de heap inconsistente")
        found.append(obj)
    if len(found) != 1:
        raise ValueError("Era esperado exatamente um relatório M2.6 por emulador")
    return found[0]


def main() -> int:
    if len(sys.argv) != 4:
        print("Uso: extract_m2_fingerprint_logcat.py logcat.txt saída.json API",
              file=sys.stderr)
        return 2
    source = pathlib.Path(sys.argv[1])
    destination = pathlib.Path(sys.argv[2])
    api = int(sys.argv[3])
    doc = parse(source.read_text(encoding="utf-8", errors="replace"), api)
    destination.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"M2.6 API{api}: 4 comparações ABBA de 8.192 caminhos válidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
