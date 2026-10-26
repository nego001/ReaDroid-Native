#!/usr/bin/env python3
"""PE-A2: guarded, offline Ghidra Headless runner for PE files on Linux.

Analyzes an isolated COPY of a PE32/PE32+ file. Ghidra parses the binary but
DOES NOT run its executable code. This runner does not constitute an OS sandbox:
run untrusted binaries as a restricted user/VM until sandboxing is implemented.

Ghidra must already be installed locally. No network, model API, or manual
Ghidra UI step is part of the runner. The export is only a bounded list of
function entry points and names (possibly generated), not decompiled source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

from pe_auto_inventory import PEProbeError, inspect_pe
from pe_ghidra_sandbox import build_command, SandboxUnavailable

MAX_RESULT_BYTES = 128 * 1024
MAX_DEEP_BYTES = 64 * 1024
MAX_DEEP_FUNCTIONS = 8
MAX_DEEP_CALLS = 12
MAX_DEEP_PSEUDOCODE = 1800
DEEP_SCRIPT_NAME = "NegrescoDeepPreview.java"
MAX_FUNCTIONS = 256
DEFAULT_TIMEOUT_SECONDS = 600
MAX_TIMEOUT_SECONDS = 1800
MAX_BINARY_BYTES = 1024 * 1024 * 1024
SCRIPT_NAME = "NegrescoFunctionInventory.java"
SCRIPT_FOLDER = Path(__file__).resolve().parent / "ghidra_scripts"
ADDRESS = re.compile(r"[0-9A-Fa-f]{1,16}\Z")


class HeadlessError(RuntimeError):
    """Preflight failure, timeout, failure of Ghidra, or invalid evidence."""


def _binary_snapshot(source: Path, target: Path) -> str:
    """Open the file without following a symlink, copy bounded bytes, hash it."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise HeadlessError("Executável de entrada indisponível") from exc
    with os.fdopen(descriptor, "rb") as original:
        meta = os.fstat(original.fileno())
        if not stat.S_ISREG(meta.st_mode) or not 128 <= meta.st_size <= MAX_BINARY_BYTES:
            raise HeadlessError("Arquivo PE não regular ou maior que 1 GiB")
        digest = hashlib.sha256()
        copied = 0
        with target.open("xb") as dest:
            while True:
                part = original.read(64 * 1024)
                if not part:
                    break
                copied += len(part)
                if copied > MAX_BINARY_BYTES:
                    raise HeadlessError("Entrada cresceu acima de 1 GiB durante a cópia")
                dest.write(part)
                digest.update(part)
        if copied != meta.st_size:
            raise HeadlessError("Entrada mudou de tamanho durante a cópia")
        # Check the copy. Never let the original path reach Ghidra.
        inspect_pe(target)
        return digest.hexdigest()


def _validated_function_evidence(path: Path) -> dict:
    try:
        if not path.is_file() or path.stat().st_size > MAX_RESULT_BYTES:
            raise HeadlessError("Ghidra não produziu uma prévia dentro da cota")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HeadlessError("Relatório do Ghidra ausente ou inválido") from exc
    if not isinstance(data, dict) or data.get("schema") != "ghidra_function_preview_v1":
        raise HeadlessError("Esquema de inventário Ghidra inesperado")
    count = data.get("total_discovered")
    functions = data.get("functions")
    truncation = data.get("preview_truncated")
    if (type(count) is not int or count < 0
            or not isinstance(functions, list) or len(functions) > MAX_FUNCTIONS
            or len(functions) > count
            or type(truncation) is not bool or truncation != (count > len(functions))
            or data.get("name_provenance") != "original_or_generated_not_verified"):
        raise HeadlessError("Contagem ou proveniência de funções inválida")
    seen = set()
    output = []
    for entry in functions:
        if not isinstance(entry, dict):
            raise HeadlessError("Registro de função com formato inválido")
        address, name, thunk = (
            entry.get("entry_point"), entry.get("name"), entry.get("is_thunk"))
        if (not isinstance(address, str) or not ADDRESS.fullmatch(address)
                or address.lower() in seen
                or not isinstance(name, str) or not 1 <= len(name) <= 160
                or type(thunk) is not bool
                or any(ord(c) < 32 or ord(c) == 127 for c in name)):
            raise HeadlessError("Identificador de função malformado")
        seen.add(address.lower())
        output.append({"entry_point": address, "name": name, "is_thunk": thunk})
    return {
        "total_discovered": count,
        "preview_truncated": truncation,
        "functions": output,
        "name_provenance": "original_or_generated_not_verified",
    }




def _validated_deep_evidence(path: Path) -> dict:
    """Fail closed on malformed or exaggerated Ghidra pseudocode evidence."""
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_DEEP_BYTES:
            raise HeadlessError("Prévia de pseudocódigo ausente ou acima do orçamento")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HeadlessError("Prévia de pseudocódigo indisponível ou corrompida") from exc
    if not isinstance(raw, dict) or raw.get("schema") != "ghidra_deep_preview_v1":
        raise HeadlessError("Esquema de pseudocódigo inesperado")
    records = raw.get("functions")
    scanned = raw.get("candidates_scanned")
    eligible = raw.get("eligible_non_thunks")
    truncated = raw.get("sample_truncated")
    if (not isinstance(records, list) or len(records) > MAX_DEEP_FUNCTIONS
            or type(scanned) is not int or not 0 <= scanned <= 256
            or type(eligible) is not int or not len(records) <= eligible <= scanned
            or type(truncated) is not bool
            or truncated != (eligible > len(records) or scanned == 256)
            or raw.get("provenance") != "ghidra_heuristic_not_original_source"):
        raise HeadlessError("Contagens de pseudocódigo inconsistentes")
    seen = set()
    cleaned = []
    for record in records:
        if not isinstance(record, dict):
            raise HeadlessError("Entrada de função inválida")
        addr = record.get("entry_point")
        name = record.get("name")
        calls = record.get("calls")
        status = record.get("decompile_status")
        pseudocode = record.get("pseudocode")
        cut = record.get("pseudocode_truncated")
        calls_cut = record.get("calls_truncated")
        if (not isinstance(addr, str) or not ADDRESS.fullmatch(addr)
                or addr.lower() in seen
                or not isinstance(name, str) or not 1 <= len(name) <= 160
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or not isinstance(calls, list) or len(calls) > MAX_DEEP_CALLS
                or any(not isinstance(x, str) or not ADDRESS.fullmatch(x) for x in calls)
                or len(set(x.lower() for x in calls)) != len(calls)
                or type(calls_cut) is not bool
                or status not in ("ok", "unavailable", "timed_out")
                or not isinstance(pseudocode, str) or len(pseudocode) > MAX_DEEP_PSEUDOCODE
                or type(cut) is not bool
                or (status != "ok" and (pseudocode or cut))
                or (status == "ok" and not pseudocode)):
            raise HeadlessError("Pseudocódigo, referências ou endereço inválido")
        seen.add(addr.lower())
        cleaned.append({
            "entry_point": addr, "name": name,
            "calls": calls, "calls_truncated": calls_cut,
            "decompile_status": status,
            "pseudocode": pseudocode, "pseudocode_truncated": cut,
        })
    return {
        "functions": cleaned,
        "candidates_scanned": scanned,
        "eligible_non_thunks": eligible,
        "sample_truncated": truncated,
        "provenance": "ghidra_heuristic_not_original_source",
    }

def _locate_ghidra(home: Path) -> Path:
    if not home.is_absolute():
        raise HeadlessError("GHIDRA_HOME deve ser um caminho absoluto")
    launcher = home / "support" / "analyzeHeadless"
    if launcher.is_symlink() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise HeadlessError("Ghidra Headless não encontrado ou não executável")
    script = SCRIPT_FOLDER / SCRIPT_NAME
    if script.is_symlink() or not script.is_file():
        raise HeadlessError("Script de exportação Ghidra indisponível")
    deep_script = SCRIPT_FOLDER / DEEP_SCRIPT_NAME
    if deep_script.is_symlink() or not deep_script.is_file():
        raise HeadlessError("Script de pseudocódigo Ghidra indisponível")
    return launcher


def inspect_functions(binary: str | Path, ghidra_home: str | Path,
                      output: str | Path, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
                      *, sandbox_mode: str = "bwrap", deep_preview: bool = False) -> dict:
    """Run trusted Ghidra tooling and atomically write bounded JSON evidence."""
    if sys.platform != "linux":
        raise HeadlessError("PE-A2 suporta somente Linux; Windows será validado depois")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise HeadlessError("Timeout fora de 1 a 1800 segundos")
    if type(deep_preview) is not bool:
        raise HeadlessError("Configuração de pseudocódigo inválida")
    if sandbox_mode not in ("bwrap", "trusted-fixture"):
        raise HeadlessError("Modo de isolamento inválido")
    target = Path(binary)
    destination = Path(output)
    if destination.exists() or destination.is_symlink():
        raise HeadlessError("Destino já existe; sobrescrita desativada")
    if not destination.parent.is_dir():
        raise HeadlessError("Diretório de saída não existe")
    if target.is_symlink():
        raise HeadlessError("Arquivo de entrada não pode ser link simbólico")
    launcher = _locate_ghidra(Path(ghidra_home))

    with tempfile.TemporaryDirectory(prefix="negresco-pe-a2-") as private:
        working = Path(private)
        snapshot = working / "input.exe"
        sha256 = _binary_snapshot(target, snapshot)
        header = inspect_pe(snapshot)
        project = working / "project"
        project.mkdir(mode=0o700)
        raw_result = working / "ghidra-functions.json"
        log_path = working / "ghidra.log"
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(working),
            "TMPDIR": str(working),
            "XDG_CACHE_HOME": str(working),
            "LANG": "C.UTF-8",
            "GHIDRA_HEADLESS_MAXMEM": "2G",
        }
        if os.environ.get("JAVA_HOME"):
            env["JAVA_HOME"] = os.environ["JAVA_HOME"]
        if sandbox_mode == "bwrap":
            scripts = working / "scripts"
            scripts.mkdir(mode=0o700)
            shutil.copyfile(SCRIPT_FOLDER / SCRIPT_NAME, scripts / SCRIPT_NAME)
            if deep_preview:
                shutil.copyfile(SCRIPT_FOLDER / DEEP_SCRIPT_NAME, scripts / DEEP_SCRIPT_NAME)
            # Fail closed if Bubblewrap or the host user namespace is unavailable.
            try:
                command = build_command(Path(ghidra_home), working, timeout_seconds,
                                        deep_preview=deep_preview)
            except (SandboxUnavailable, OSError) as exc:
                raise HeadlessError("Isolamento Bubblewrap indisponível; análise recusada") from exc
        else:
            # Explicit test-only compatibility path for synthetic fixtures in
            # CI. Never choose this automatically when inspecting unknown files.
            command = [
                str(launcher), str(project), "NegrescoAutomaticPE",
                "-import", str(snapshot),
                "-scriptPath", str(SCRIPT_FOLDER),
                "-postScript", SCRIPT_NAME, str(raw_result),
                "-analysisTimeoutPerFile", str(max(1, timeout_seconds - 30)),
                "-max-cpu", "2",
                "-readOnly", "-deleteProject",
                "-log", str(log_path),
            ]
            if deep_preview:
                insert_at = command.index("-analysisTimeoutPerFile")
                command[insert_at:insert_at] = [
                    "-postScript", DEEP_SCRIPT_NAME, str(working / "ghidra-deep.json"),
                ]
        # Pass a fixed argv array, without a shell. The inspected program is only
        # file passed to Ghidra: this process is trusted local Ghidra itself.
        try:
            process = subprocess.Popen(
                command, cwd=working, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise HeadlessError("Não foi possível iniciar o Ghidra instalado") from exc
        try:
            code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise HeadlessError("Ghidra excedeu o tempo e foi interrompido") from exc
        if code != 0:
            raise HeadlessError("O Ghidra não concluiu a análise; nenhum relatório foi aceito")
        evidence = _validated_function_evidence(raw_result)
        deep = (_validated_deep_evidence(working / "ghidra-deep.json")
                if deep_preview else None)
        report = {
            "schema": "pe_ghidra_headless_v1",
            "source_sha256": sha256,
            "format": header["format"],
            "architecture": header["architecture"],
            "evidence": evidence,
            "deep_preview": deep,
            "limitations": {
                "status": "function-entrypoints-preview-only",
                "original_names_guaranteed": False,
                "pseudocode": ("bounded_heuristic_preview" if deep_preview
                               else "not_implemented"),
                "call_graph": ("bounded_direct_references" if deep_preview
                              else "not_implemented"),
                "behavioral_classification": "not_implemented",
                "executable_launched": False,
                "os_sandbox": ("bubblewrap_profile" if sandbox_mode == "bwrap"
                               else "not_implemented"),
            },
        }
        encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        if len(encoded) > MAX_RESULT_BYTES:
            raise HeadlessError("Relatório final acima do limite")
        # Write into the destination filesystem, then link atomically with
        # exclusive creation. A failed write cannot expose partial JSON.
        staging = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="wb", prefix=".negresco-a2-", suffix=".tmp",
                    dir=destination.parent, delete=False) as saved:
                staging = Path(saved.name)
                saved.write(encoded)
                saved.write(b"\n")
                saved.flush()
                os.fsync(saved.fileno())
            os.link(staging, destination)  # fails if destination already exists
        except OSError as exc:
            raise HeadlessError("Não foi possível criar relatório sem sobrescrever arquivos") from exc
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
        return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Negresco PE-A2: análise estática automatizada via Ghidra Headless")
    parser.add_argument("binary", type=Path)
    parser.add_argument("--ghidra-home", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", default=DEFAULT_TIMEOUT_SECONDS, type=int)
    parser.add_argument("--deep-preview", action="store_true",
                        help="Recuperar amostra limitada de chamadas e pseudocódigo")
    parser.add_argument("--allow-unisolated-synthetic-fixture", action="store_true",
                        help="Somente para CI com PE sintético confiável; desativa isolamento")
    args = parser.parse_args(argv)
    try:
        report = inspect_functions(args.binary, args.ghidra_home, args.output,
                                   args.timeout_seconds,
                                   deep_preview=args.deep_preview,
                                   sandbox_mode=("trusted-fixture"
                                       if args.allow_unisolated_synthetic_fixture
                                       else "bwrap"))
    except (HeadlessError, PEProbeError, OSError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "completed", "functions_previewed": len(report["evidence"]["functions"]),
        "total_discovered": report["evidence"]["total_discovered"],
        "report": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
