"""Verify the exact installed Ghidra 12.2 tree against its pinned release ZIP.

Version metadata is not authenticity. This function first hashes the *entire*
upstream ZIP, then compares every shipped file against the extracted tree,
rejecting symlinks, traversal, duplicates and unlisted files. This is a
local, offline trust check before running real Ghidra in the Arch VM.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import zipfile

GHIDRA_RELEASE_SHA256 = "2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67"
GHIDRA_RELEASE_ROOT = "ghidra_12.2_PUBLIC"


class GhidraIntegrityError(RuntimeError):
    pass


def _hash_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def verify_pinned_ghidra_tree(ghidra_home: Path, release_zip: Path) -> dict:
    """Fully verify a trusted extracted Ghidra tree against the pinned ZIP."""
    home = Path(ghidra_home)
    archive = Path(release_zip)
    if not home.is_absolute() or not archive.is_absolute():
        raise GhidraIntegrityError("Ghidra and release ZIP require absolute paths")
    try:
        if (home.is_symlink() or not home.is_dir()
                or archive.is_symlink() or not archive.is_file()):
            raise GhidraIntegrityError("Ghidra tree or ZIP unavailable")
        if not stat.S_ISREG(archive.stat().st_mode):
            raise GhidraIntegrityError("Release archive is not regular")
        with archive.open("rb") as inp:
            sha = _hash_stream(inp)
        if sha != GHIDRA_RELEASE_SHA256:
            raise GhidraIntegrityError("Pinned Ghidra release SHA-256 mismatch")
        expected_files: set[str] = set()
        with zipfile.ZipFile(archive, "r") as source:
            for member in source.infolist():
                name = member.filename
                pure = PurePosixPath(name)
                parts = pure.parts
                if (not parts or parts[0] != GHIDRA_RELEASE_ROOT
                        or any(part in (".", "..", "") for part in parts)
                        or pure.is_absolute() or "\\" in name
                        or name.rstrip("/") != str(pure).rstrip("/")
                        or member.flag_bits & 0x1):
                    raise GhidraIntegrityError("Unsafe member in pinned Ghidra archive")
                if len(parts) == 1:
                    if not member.is_dir():
                        raise GhidraIntegrityError("Unexpected archive root file")
                    continue
                relative = Path(*parts[1:])
                destination = home / relative
                if any(parent.is_symlink() for parent in
                       [home, *(home / Path(*parts[1:i])
                                for i in range(2, len(parts) + 1))]):
                    raise GhidraIntegrityError("Symlink inside extracted Ghidra tree")
                if member.is_dir():
                    if not destination.is_dir():
                        raise GhidraIntegrityError("Missing Ghidra directory")
                    continue
                mode = (member.external_attr >> 16) & 0o170000
                if mode not in (0, stat.S_IFREG):
                    raise GhidraIntegrityError("Non-regular Ghidra ZIP member")
                key = relative.as_posix()
                if key in expected_files:
                    raise GhidraIntegrityError("Duplicate Ghidra archive entry")
                expected_files.add(key)
                if not destination.is_file() or destination.is_symlink():
                    raise GhidraIntegrityError("Missing or linked Ghidra release file")
                with source.open(member) as upstream, destination.open("rb") as local:
                    if _hash_stream(upstream) != _hash_stream(local):
                        raise GhidraIntegrityError("Ghidra installed file differs from pinned ZIP")
        if not expected_files:
            raise GhidraIntegrityError("Pinned Ghidra archive contains no files")
        actual_files: set[str] = set()
        for folder, dirs, files in os.walk(home, followlinks=False):
            current = Path(folder)
            for dirname in dirs:
                if (current / dirname).is_symlink():
                    raise GhidraIntegrityError("Symlink in installed Ghidra directories")
            for filename in files:
                path = current / filename
                if path.is_symlink() or not path.is_file():
                    raise GhidraIntegrityError("Unexpected file type in Ghidra installation")
                actual_files.add(path.relative_to(home).as_posix())
        if actual_files != expected_files:
            raise GhidraIntegrityError("Unlisted or missing Ghidra installation files")
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile,
            zipfile.LargeZipFile, RuntimeError) as exc:
        if isinstance(exc, GhidraIntegrityError):
            raise
        raise GhidraIntegrityError("Ghidra release integrity could not be verified") from exc
    return {"verified": True, "release_sha256": sha,
            "matched_files": len(expected_files),
            "symlinks_allowed": False, "unexpected_files_allowed": False}
