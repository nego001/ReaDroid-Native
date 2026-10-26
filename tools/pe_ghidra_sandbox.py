"""PE-A2.1 hardened optional Bubblewrap profile for Ghidra on Arch/Linux.

No host home, project repositories, or network namespaces are exposed to the
analyzer. Only read-only system runtime, a read-only verified Ghidra tree,
and one private, writable work directory are mounted.

This is not a hardware VM or an absolute security guarantee. Requires
unprivileged user namespaces supported by the Linux host. Fail closed when
Bubblewrap is absent. CI may explicitly run only synthetic fixtures outside
this profile to test headless compatibility.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat

class SandboxUnavailable(RuntimeError):
    pass

def build_command(ghidra_home: Path, working: Path,
                  timeout_seconds: int, *, bwrap_path: str | None = None) -> list[str]:
    """Produce a deterministic Bubblewrap argv. No subprocess is started here."""
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise SandboxUnavailable("Timeout inválido para sandbox")
    executable = bwrap_path if bwrap_path is not None else shutil.which("bwrap")
    if not executable:
        raise SandboxUnavailable("Bubblewrap ausente: análise recusada sem isolamento")
    launcher = Path(executable)
    if launcher.is_symlink() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise SandboxUnavailable("Executável Bubblewrap indisponível ou não confiável")
    if os.geteuid() == 0:
        raise SandboxUnavailable("Não executar Ghidra em sandbox como root")
    root = Path(ghidra_home).resolve(strict=True)
    workspace = Path(working).resolve(strict=True)
    if not root.is_dir() or not workspace.is_dir():
        raise SandboxUnavailable("Diretório de Ghidra ou workspace inválido")
    if root == workspace or root in workspace.parents or workspace in root.parents:
        raise SandboxUnavailable("Workspace não pode sobrepor instalação do Ghidra")
    if not (workspace / "scripts" / "NegrescoFunctionInventory.java").is_file():
        raise SandboxUnavailable("Exportador Ghidra não preparado no workspace")
    if not (root / "support" / "analyzeHeadless").is_file():
        raise SandboxUnavailable("Instalação Ghidra incompleta")
    if not Path("/usr").is_dir():
        raise SandboxUnavailable("Runtime Linux /usr indisponível")

    argv = [str(launcher), "--die-with-parent", "--unshare-all", "--new-session",
            "--clearenv",
            "--ro-bind", "/usr", "/usr"]
    # Only system paths needed to start Java: /bin and /lib are usually
    # symlinks into /usr on Arch, but support separate system mounts too.
    for system in ("/bin", "/lib", "/lib64", "/sbin"):
        item = Path(system)
        if item.is_symlink():
            target = os.readlink(item)
            if target.startswith("/"):
                if target.startswith("/usr/"):
                    argv += ["--symlink", target[1:], system]
                else:
                    raise SandboxUnavailable("Symlink de runtime fora de /usr")
            elif target.startswith("usr/"):
                argv += ["--symlink", target, system]
            else:
                raise SandboxUnavailable("Link de runtime não permitido")
        elif item.is_dir():
            argv += ["--ro-bind", system, system]

    argv += ["--dir", "/opt", "--ro-bind", str(root), "/opt/negresco-ghidra",
             "--dir", "/work", "--bind", str(workspace), "/work",
             "--dir", "/etc", "--tmpfs", "/tmp", "--tmpfs", "/home",
             "--proc", "/proc", "--dev", "/dev",
             "--setenv", "HOME", "/work",
             "--setenv", "XDG_CACHE_HOME", "/work",
             "--setenv", "TMPDIR", "/tmp",
             "--setenv", "PATH", "/usr/bin:/bin",
             "--setenv", "LANG", "C.UTF-8"]
    # JDK installed through pacman usually lives under /usr/lib/jvm.
    java_home = os.environ.get("JAVA_HOME", "")
    if java_home:
        resolved = Path(java_home).resolve(strict=False)
        if resolved == Path("/usr") or Path("/usr") in resolved.parents:
            argv += ["--setenv", "JAVA_HOME", str(resolved)]
    argv += [
        "--chdir", "/work", "--",
        "/opt/negresco-ghidra/support/analyzeHeadless",
        "/work/project", "NegrescoAutomaticPE",
        "-import", "/work/input.exe",
        "-scriptPath", "/work/scripts",
        "-postScript", "NegrescoFunctionInventory.java",
        "/work/ghidra-functions.json",
        "-analysisTimeoutPerFile", str(max(1, timeout_seconds - 30)),
        "-max-cpu", "2", "-readOnly", "-deleteProject",
        "-log", "/work/ghidra.log",
    ]
    return argv
