"""Optional strict cgroup v2 scope around a Bubblewrap Ghidra invocation.

This is a *request* for kernel-enforced, per-scope budgets, not a substitute
for verifying the resulting cgroup on the target host. It deliberately never
executes a command or silently falls back to unbounded analysis.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

MEMORY_MAX_BYTES = 4 * 1024 * 1024 * 1024
TASKS_MAX = 128
CPU_QUOTA_PERCENT = 200


class ResourceLimitsUnavailable(RuntimeError):
    """Dedicated cgroup v2 resource limits cannot be requested safely."""


def wrap_in_cgroup_scope(command: list[str], *,
                         systemd_run_path: str | None = None) -> list[str]:
    """Create argv for a synchronous systemd user scope, never a shell string.

    The user manager must accept MemoryMax/TasksMax/CPUQuota and create the
    scope. Any error from systemd-run must reject the analysis; callers must
    not retry the command without the scope.
    """
    if not isinstance(command, list) or not command or any(
            not isinstance(arg, str) or not arg for arg in command):
        raise ResourceLimitsUnavailable("Comando de sandbox inválido")
    if os.geteuid() == 0:
        raise ResourceLimitsUnavailable("Escopo de Ghidra não pode rodar como root")
    if not Path("/sys/fs/cgroup/cgroup.controllers").is_file():
        raise ResourceLimitsUnavailable("Host sem cgroup v2 visível")
    executable = (systemd_run_path if systemd_run_path is not None
                  else shutil.which("systemd-run"))
    if not executable:
        raise ResourceLimitsUnavailable("systemd-run ausente; limites obrigatórios")
    launcher = Path(executable)
    if launcher.is_symlink() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ResourceLimitsUnavailable("systemd-run indisponível ou não confiável")
    verifier = Path(__file__).with_name("pe_cgroup_guard.py")
    if verifier.is_symlink() or not verifier.is_file():
        raise ResourceLimitsUnavailable("Verificador cgroup ausente ou não confiável")
    return [
        str(launcher), "--user", "--scope", "--quiet",
        "--property=MemoryMax=" + str(MEMORY_MAX_BYTES),
        "--property=TasksMax=" + str(TASKS_MAX),
        "--property=CPUQuota=" + str(CPU_QUOTA_PERCENT) + "%",
        "--", sys.executable, "-I", str(verifier.resolve(strict=True)),
        str(MEMORY_MAX_BYTES), str(TASKS_MAX), str(CPU_QUOTA_PERCENT),
        "--", *command,
    ]
