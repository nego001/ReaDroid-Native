#!/usr/bin/env python3
"""PE-A4.1: conservative offline behavior hypotheses from Ghidra evidence.

Require either a recognized call expression in recovered C or a verified
external callee reference from the Ghidra call graph. Global PE imports
are corroboration ONLY. Neither implies runtime behavior.
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
    # Only already-selected Ghidra entrypoints are named in the context.
    # Calls outside the preview remain unclassified references, not guessed names.
    selected_names = {
        item["entry_point"].lower(): item["name"]
        for item in functions
        if isinstance(item, dict)
        and isinstance(item.get("entry_point"), str)
        and isinstance(item.get("name"), str)
    }
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
        api_refs = item.get("api_call_references", [])
        if (not isinstance(api_refs, list) or len(api_refs) > 8
                or any(not isinstance(api, str) or api.lower() not in API_TO_RULE
                       for api in api_refs)
                or len({api.lower() for api in api_refs}) != len(api_refs)):
            raise ValueError("Referências externas de API adulteradas")
        # String evidence is contextual only: never promote its wording
        # into a behavioral category. These bytes stay in the LOCAL report.
        strings = item.get("strings", [])
        calls = item.get("calls", [])
        if (not isinstance(strings, list) or len(strings) > 8
                or not isinstance(calls, list) or len(calls) > 24):
            raise ValueError("Contexto de strings/chamadas fora do limite")
        context_strings = []
        for s in strings:
            if (not isinstance(s, dict) or not isinstance(s.get("text"), str)
                    or not 6 <= len(s["text"]) <= 96
                    or not isinstance(s.get("data_address"), str)
                    or not isinstance(s.get("reference_from"), str)):
                raise ValueError("Contexto de string não validado")
            context_strings.append({
                "text": s["text"], "data_address": s["data_address"],
                "reference_from": s["reference_from"],
            })
        related = []
        seen_related = set()
        for address in calls:
            if not isinstance(address, str):
                raise ValueError("Chamada interna inválida")
            key = address.lower()
            if key in selected_names and key not in seen_related and key != entry.lower():
                seen_related.add(key)
                related.append({"entry_point": address, "name": selected_names[key]})
            if len(related) >= 8:
                break
        hypotheses = []
        # Maintain provenance for each API. Do not turn an import table entry
        # or a function name into a call when no Ghidra evidence exists.
        observed: dict[str, dict[str, set[str]]] = {}
        for api in api_refs:
            category, _ = API_TO_RULE[api.lower()]
            observed.setdefault(category, {}).setdefault(
                api.lower(), set()).add("ghidra_external_callee")
        if status == "ok" and source:
            scrubbed = _remove_comments_and_literals(source)
            # The first signature in generated C can be a function
            # declaration, not a call. Require a body before matching.
            function_body = scrubbed.partition("{")[2]
            for match in _CALL.finditer(function_body):
                api_name = match.group(1)
                label = API_TO_RULE.get(api_name.lower())
                if not label:
                    continue
                category, _ = label
                observed.setdefault(category, {}).setdefault(
                    api_name.lower(), set()).add("pseudocode_call")
        for category, label, _apis in RULES:
                evidence = observed.get(category, {})
                if not evidence:
                    continue
                api_names = sorted(evidence)
                corroborated = [api for api in api_names if api.lower() in imports]
                hypotheses.append({
                    "category": category,
                    "explanation": label,
                    "confidence": ("moderada" if len(api_names) >= 2
                                   and corroborated and
                                   not item.get("pseudocode_truncated")
                                   else "baixa"),
                    "evidence": [
                        {"kind": (
                            "pseudocode_api_call"
                            if evidence[api] == {"pseudocode_call"}
                            else "ghidra_external_callee"
                            if evidence[api] == {"ghidra_external_callee"}
                            else "pseudocode_and_ghidra_callee"
                        ), "api": api,
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
            "string_context": context_strings,
            "strings_are_behavior_evidence": False,
            "linked_selected_callees": related,
            "context_provenance": "ghidra_direct_static_references_only",
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
        "scope": "bounded_ghidra_decompilation_and_references_only",
        "limitations": (
            "Pistas estáticas e nomes WinAPI não provam intenção, execução, "
            "capacidade completa de desinstalação ou código-fonte original."
        ),
    }
