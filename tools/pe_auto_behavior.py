#!/usr/bin/env python3
"""PE-A4: conservative, OFFLINE classification from bounded Ghidra evidence.

Every hypothesis requires a call to a specific Windows API visible in recovered
pseudocode. Global PE imports only corroborate and never prove that a function
calls an API or that any action occurs at runtime.
"""
from __future__ import annotations

import re

MAX_FUNCTIONS = 12
MAX_SNIPPET_CHARS = 1800
MAX_HYPOTHESES_PER_FUNCTION = 3
MAX_EVIDENCE_PER_CATEGORY = 4

RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("filesystem_inspection", "Consulta metadados e nomes de arquivos",
     ("GetFileAttributesA", "GetFileAttributesW", "FindFirstFileA",
      "FindFirstFileW", "FindNextFileA", "FindNextFileW",
      "GetFileInformationByHandle")),
    ("filesystem_modification", "Pode modificar arquivos ou diretórios",
     ("DeleteFileA", "DeleteFileW", "RemoveDirectoryA", "RemoveDirectoryW",
      "MoveFileExA", "MoveFileExW", "SetFileAttributesA",
      "SetFileAttributesW", "CopyFileA", "CopyFileW",
      "CreateDirectoryA", "CreateDirectoryW")),
    ("registry_read", "Consulta chaves ou valores do Registro do Windows",
     ("RegOpenKeyExA", "RegOpenKeyExW", "RegQueryValueExA",
      "RegQueryValueExW", "RegEnumKeyExA", "RegEnumKeyExW",
      "RegGetValueA", "RegGetValueW")),
    ("registry_write", "Pode modificar chaves ou valores do Registro do Windows",
     ("RegSetValueExA", "RegSetValueExW", "RegDeleteKeyA",
      "RegDeleteKeyW", "RegDeleteValueA", "RegDeleteValueW",
      "RegCreateKeyExA", "RegCreateKeyExW")),
    ("service_management", "Interage com o gerenciador de serviços Windows",
     ("OpenSCManagerA", "OpenSCManagerW", "OpenServiceA",
      "OpenServiceW", "DeleteService", "ControlService",
      "CreateServiceA", "CreateServiceW", "StartServiceA",
      "StartServiceW")),
    ("process_management", "Interage com processos Windows",
     ("CreateProcessA", "CreateProcessW", "TerminateProcess",
      "OpenProcess", "EnumProcesses")),
    ("network_request", "Utiliza APIs Windows de requisições de rede",
     ("WinHttpConnect", "WinHttpSendRequest", "WinHttpReceiveResponse",
      "InternetConnectA", "InternetConnectW", "HttpSendRequestA",
      "HttpSendRequestW")),
    ("msi_package_management", "Interage com a gestão de pacotes MSI",
     ("MsiConfigureProductA", "MsiConfigureProductW",
      "MsiConfigureProductExA", "MsiConfigureProductExW",
      "MsiInstallProductA", "MsiInstallProductW")),
)

API_TO_RULE = {
    api.lower(): (category, label)
    for category, label, names in RULES for api in names
}
_CALL = re.compile(r"\b(?:__imp_)?([A-Za-z][A-Za-z0-9_]*)\s*\(", re.ASCII)


def _remove_comments_and_literals(text: str) -> str:
    """Conservatively erase comments, quoted strings and character literals."""
    out: list[str] = []
    state = "code"
    pos = 0
    while pos < len(text):
        ch = text[pos]
        following = text[pos + 1] if pos + 1 < len(text) else ""
        if state == "code":
            if ch == "/" and following == "/":
                state = "line"
                out.extend((" ", " "))
                pos += 2
                continue
            if ch == "/" and following == "*":
                state = "block"
                out.extend((" ", " "))
                pos += 2
                continue
            if ch in ('"', "'"):
                state = ch
                out.append(" ")
                pos += 1
                continue
            out.append(ch)
        elif state == "line":
            if ch == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" ")
        elif state == "block":
            if ch == "*" and following == "/":
                state = "code"
                out.extend((" ", " "))
                pos += 2
                continue
            out.append("\n" if ch == "\n" else " ")
        else:
            if ch == "\\" and following:
                out.extend((" ", " "))
                pos += 2
                continue
            if ch == state:
                state = "code"
            out.append("\n" if ch == "\n" else " ")
        pos += 1
    return "".join(out)


def _global_import_names(symbols: dict | None) -> frozenset[str]:
    """PE-A1 imports corroborate a pattern but never create hypotheses."""
    if not isinstance(symbols, dict) or symbols.get("schema") != "pe_symbol_inventory_v1":
        return frozenset()
    found: set[str] = set()
    imports = symbols.get("imports", [])
    if not isinstance(imports, list):
        return frozenset()
    for item in imports[:128]:
        if not isinstance(item, dict):
            continue
        functions = item.get("functions", [])
        if not isinstance(functions, list):
            continue
        for member in functions[:512]:
            if isinstance(member, dict) and member.get("by") == "name":
                name = member.get("name")
                if isinstance(name, str) and len(name) <= 256:
                    found.add(name.lower())
    return frozenset(found)


def classify(deep: dict, symbols: dict | None = None) -> dict:
    """Classify only already-validated Ghidra deep_preview evidence.

    Unknown is the default. No cloud model, execution, binary upload or
    source-code authenticity claim is involved.
    """
    if not isinstance(deep, dict) or deep.get("provenance") != (
            "ghidra_heuristic_not_original_source"):
        raise ValueError("Prévia Ghidra ausente ou sem proveniência validada")
    functions = deep.get("functions")
    if not isinstance(functions, list) or len(functions) > MAX_FUNCTIONS:
        raise ValueError("Amostra Ghidra fora do limite")
    imports = _global_import_names(symbols)
    results: list[dict] = []
    for item in functions:
        if not isinstance(item, dict):
            raise ValueError("Função Ghidra inválida")
        entry = item.get("entry_point")
        name = item.get("name")
        status = item.get("decompile_status")
        source = item.get("pseudocode")
        if (not isinstance(entry, str)
                or not re.fullmatch(r"[a-fA-F0-9]{1,16}", entry)
                or not isinstance(name, str) or len(name) > 160
                or not isinstance(source, str) or len(source) > MAX_SNIPPET_CHARS
                or status not in ("ok", "unavailable", "timed_out")):
            raise ValueError("Função Ghidra adulterada ou fora do limite")
        hypotheses = []
        if status == "ok" and source:
            calls_by_category: dict[str, dict[str, str]] = {}
            for match in _CALL.finditer(_remove_comments_and_literals(source)):
                api_name = match.group(1)
                label = API_TO_RULE.get(api_name.lower())
                if not label:
                    continue
                category, _ = label
                calls_by_category.setdefault(category, {})[api_name.lower()] = api_name
            for category, label, _apis in RULES:
                evidence = calls_by_category.get(category, {})
                if not evidence:
                    continue
                api_names = [evidence[k] for k in sorted(evidence)]
                corroborated = [api for api in api_names if api.lower() in imports]
                hypotheses.append({
                    "category": category,
                    "explanation": label,
                    "confidence": ("moderada" if len(api_names) >= 2
                                   and corroborated and
                                   not item.get("pseudocode_truncated")
                                   else "baixa"),
                    "evidence": [
                        {"kind": "pseudocode_api_call", "api": api,
                         "import_table_corrob": api.lower() in imports}
                        for api in api_names[:MAX_EVIDENCE_PER_CATEGORY]
                    ],
                    "evidence_count": len(api_names),
                    "inference": "static_call_pattern_not_runtime_proof",
                })
        hypotheses.sort(key=lambda h: (-h["evidence_count"], h["category"]))
        results.append({
            "entry_point": entry,
            "name": name,
            "status": "hypotheses" if hypotheses else "unidentified",
            "hypotheses": hypotheses[:MAX_HYPOTHESES_PER_FUNCTION],
            "hypotheses_truncated": len(hypotheses) > MAX_HYPOTHESES_PER_FUNCTION,
            "evidence_quality": ("partial_pseudocode"
                if item.get("pseudocode_truncated") else "bounded_pseudocode"),
        })
    known = sum(record["status"] == "hypotheses" for record in results)
    return {
        "schema": "pe_behavior_hypotheses_v1",
        "engine": "deterministic_local_rules_not_ai",
        "functions": results,
        "functions_with_hypotheses": known,
        "functions_unidentified": len(results) - known,
        "scope": "bounded_ghidra_decompilation_only",
        "limitations": (
            "Pistas estáticas e nomes WinAPI não provam intenção, execução, "
            "capacidade completa de desinstalação ou código-fonte original."
        ),
    }
