#!/usr/bin/env python3
"""PE-S1.69: bounded pipe capture for the explicitly authorized native child.

The launched executable and argv are selected by the S1.66 reviewer launcher;
this is NOT an arbitrary command runner or VM attestation. Linux only: drain
both stdout and stderr using nonblocking reads, bound actual accumulated bytes
BEFORE memory exhaustion, and terminate the child's session on refusal.
No shell, guest, PE, network or Ghidra execution occurs in this module itself.
"""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time


class BoundedNativeChildError(RuntimeError):
    """Native process output, runtime or launch could not be accepted."""


def run_bounded_native(argv: list[str], *, env: dict[str, str],
                       timeout: float = 1800,
                       max_stdout: int = 1024 * 1024,
                       max_stderr: int = 8192) -> subprocess.CompletedProcess:
    """Capture bounded bytes from both pipes; terminate session on failure.

    Child executable security is NOT established by this function. The argv
    must already be pinned by the caller. The child has its own session so
    timeout/overflow cleanup does not kill the reviewer's Python process.
    Session descendants are killed even after a normal parent exit, but a
    child can escape into another session/systemd scope, which still requires
    the existing native scope cleanup and independent review.
    """
    if (not isinstance(argv, list) or not argv
            or any(not isinstance(a, str) or not a or "\0" in a for a in argv)
            or not isinstance(env, dict)
            or type(timeout) not in (int, float)
            or not 0 < timeout <= 1800
            or type(max_stdout) is not int or not 0 < max_stdout <= 1024 * 1024
            or type(max_stderr) is not int or not 0 < max_stderr <= 8192):
        raise BoundedNativeChildError("Invalid bounded child controls")
    process = None
    completed = False
    try:
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            close_fds=True, start_new_session=True, env=env)
        if process.stdout is None or process.stderr is None:
            raise BoundedNativeChildError("Native child pipes missing")
        outputs = {"stdout": bytearray(), "stderr": bytearray()}
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            for name, stream in (
                    ("stdout", process.stdout), ("stderr", process.stderr)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BoundedNativeChildError(
                        "Native acceptance timed out with incomplete output")
                for event, _ in selector.select(timeout=min(remaining, 0.25)):
                    name = event.data
                    stream = event.fileobj
                    limit = max_stdout if name == "stdout" else max_stderr
                    # Read at most enough bytes to detect an overflow; never
                    # buffer attacker-controlled data beyond the cap+1.
                    chunk = os.read(
                        stream.fileno(),
                        min(65536, limit + 1 - len(outputs[name])))
                    if not chunk:
                        selector.unregister(stream)
                    else:
                        outputs[name].extend(chunk)
                        if len(outputs[name]) > limit:
                            raise BoundedNativeChildError(
                                "Native acceptance " + name + " exceeds limit")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BoundedNativeChildError("Native acceptance exceeded deadline")
        exitcode = process.wait(timeout=remaining)
        completed = True
        return subprocess.CompletedProcess(
            argv, exitcode, bytes(outputs["stdout"]), bytes(outputs["stderr"]))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise BoundedNativeChildError(
            "Native child unavailable or exceeded bounded execution") from exc
    finally:
        if process is not None:
            # A child can exit successfully after spawning descendants
            # which close/inherit neither pipe. EOF + parent exit alone
            # DOES NOT prove its session has no surviving subprocesses.
            # Always retire this dedicated process group, including on
            # returncode=0 and nonzero CompletedProcess results. A process
            # which created a *different* session/scope remains outside
            # this boundary and still requires independent cleanup review.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                pass
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                process.wait(timeout=3)
