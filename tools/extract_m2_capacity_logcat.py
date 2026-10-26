#!/usr/bin/env python3
"""Extract only the synthetic M2 capacity result from Android logcat.

Gradle's connectedDebugAndroidTest removes its target package on some devices.
Do not rely on adb run-as after that command. The test emits a small JSON line
before teardown; no APK bytes, private paths or unrelated logcat are uploaded.
"""
import json
import pathlib
import sys

EXPECTED = (
    "fixture",
    "fixtureGeneration",
    "zipAdmission",
    "boundedPreview",
    "sqliteIndexBuild",
    "sqliteTailSearch",
    "securityMetadata",
)
COUNTERS = ("wallMs", "processCpuMs", "javaHeapUsedBytes",
            "nativeHeapAllocatedBytes", "processPssKib")
MARKER = "M2Capacity"
PREFIX = "RESULT_JSON:"


def parse(text: str, api: int) -> dict:
    matches = []
    for line in text.splitlines():
        if MARKER not in line or PREFIX not in line:
            continue
        payload = line.split(PREFIX, 1)[1].strip()
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("Métrica M2 registrada com JSON inválido") from error
        if not isinstance(obj, dict) or obj.get("result") != "PASS":
            raise ValueError("Métrica M2 não contém confirmação de teste aprovado")
        if not isinstance(obj.get("fixture"), dict):
            raise ValueError("Métrica M2 sem metadados sintéticos")
        fixture = obj["fixture"]
        if fixture.get("synthetic") is not True:
            raise ValueError("Métricas de corpus não sintético não serão publicadas")
        if fixture.get("deviceApi") != api:
            raise ValueError("Métricas pertencem a outra versão do Android")
        if fixture.get("fileCount") != 2502 or fixture.get("entryCount") != 2503:
            raise ValueError("Corpus medido não corresponde ao benchmark autorizado")
        if not isinstance(fixture.get("archiveBytes"), int) or fixture["archiveBytes"] <= 0:
            raise ValueError("Tamanho de arquivo sintético inválido")
        if not isinstance(fixture.get("contentBytes"), int) or fixture["contentBytes"] <= 0:
            raise ValueError("Tamanho descomprimido inválido")
        if set(obj) != set(EXPECTED) | {"result"}:
            raise ValueError("Campos inesperados ou ausentes: recusar dados arbitrários")
        for stage in EXPECTED[1:]:
            metric = obj.get(stage)
            if not isinstance(metric, dict) or metric.get("stage") != stage:
                raise ValueError("Etapa de benchmark inválida: " + stage)
            for key in COUNTERS:
                value = metric.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError("Métrica não numérica ou negativa: " + key)
            if set(metric) != set(COUNTERS) | {"stage"}:
                raise ValueError("Campos de métricas fora da lista aprovada")
        if set(fixture) != {"synthetic", "contentBytes", "archiveBytes",
                           "fileCount", "entryCount", "deviceApi"}:
            raise ValueError("Dados de fixture além da lista segura")
        matches.append(obj)
    if len(matches) != 1:
        raise ValueError(f"Esperado um único resultado M2, encontrados {len(matches)}")
    return matches[0]


def main() -> int:
    if len(sys.argv) != 4:
        print("Uso: extract_m2_capacity_logcat.py logcat.txt saída.json API", file=sys.stderr)
        return 2
    source, output, api = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), int(sys.argv[3])
    result = parse(source.read_text(encoding="utf-8", errors="replace"), api)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"M2 API{api}: {result['fixture']['entryCount']} entradas; "
          f"relatório sintético válido em {output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
