"""Verify the exact installed Ghidra 12.2 tree against its pinned release ZIP.

Version metadata is not authenticity. This function first hashes the *entire*
upstream ZIP, then compares every shipped file against the extracted tree,
rejecting symlinks, traversal, duplicates and unlisted files. This is a
local, offline trust check before running real Ghidra in the Arch VM.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import zipfile

from pe_nofollow_paths import open_absolute_directory_nofollow

GHIDRA_RELEASE_SHA256 = "2c2cd776db3c1f6a097ba418922378ac3649cadd5e844a6f5f088ae628a7be67"
GHIDRA_RELEASE_ROOT = "ghidra_12.2_PUBLIC"


class GhidraIntegrityError(RuntimeError):
    pass


def _hash_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _metadata(fd: int) -> tuple[int, int, int, int, int]:
    st = os.fstat(fd)
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _hash_installed_file(home_fd: int, relative: Path) -> str:
    """Read a pinned regular file, never following a symbolic link."""
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    with ExitStack() as handles:
        folder_fd = home_fd
        parts = relative.parts
        for part in parts[:-1]:
            folder_fd = os.open(
                part, flags | os.O_DIRECTORY, dir_fd=folder_fd)
            handles.callback(os.close, folder_fd)
        file_fd = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=folder_fd)
        handles.callback(os.close, file_fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise GhidraIntegrityError("Non-regular Ghidra release file")
        before = _metadata(file_fd)
        with os.fdopen(os.dup(file_fd), "rb") as stream:
            digest = _hash_stream(stream)
        if before != _metadata(file_fd):
            raise GhidraIntegrityError("Ghidra file changed while hashing")
        return digest


def _verify_directory(home_fd: int, relative: Path) -> None:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    with ExitStack() as handles:
        fd = home_fd
        for part in relative.parts:
            fd = os.open(part, flags, dir_fd=fd)
            handles.callback(os.close, fd)


def _list_installed_files(home_fd: int) -> set[str]:
    """List from pinned directory descriptors; reject special nodes and links."""
    actual: set[str] = set()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW

    def walk(fd: int, prefix: str) -> None:
        with os.scandir(fd) as iterator:
            entries = list(iterator)
        for entry in entries:
            name = entry.name
            if name in (".", "..") or "/" in name:
                raise GhidraIntegrityError("Invalid Ghidra tree entry")
            relative = prefix + name
            if entry.is_symlink():
                raise GhidraIntegrityError("Symlink in installed Ghidra tree")
            if entry.is_dir(follow_symlinks=False):
                child_fd = os.open(name, flags, dir_fd=fd)
                try:
                    walk(child_fd, relative + "/")
                finally:
                    os.close(child_fd)
            elif entry.is_file(follow_symlinks=False):
                file_fd = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW |
                    os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=fd)
                try:
                    if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                        raise GhidraIntegrityError(
                            "Unexpected file type in Ghidra installation")
                finally:
                    os.close(file_fd)
                actual.add(relative)
            else:
                raise GhidraIntegrityError(
                    "Unexpected file type in Ghidra installation")

    walk(home_fd, "")
    return actual


def verify_pinned_ghidra_tree(ghidra_home: Path, release_zip: Path) -> dict:
    """Compare every shipped file with a pinned, SHA-256-verified release ZIP.

    All path ancestors and tree entries are opened without following links.
    File descriptors protect the observed bytes against name replacement
    during hashing. This does not protect the later Ghidra launch from a
    privileged adversary modifying the installed files after verification.
    """
    home = Path(ghidra_home)
    archive = Path(release_zip)
    if not home.is_absolute() or not archive.is_absolute():
        raise GhidraIntegrityError("Ghidra and release ZIP require absolute paths")
    try:
        with ExitStack() as handles:
            home_fd = open_absolute_directory_nofollow(home, handles)
            zip_parent_fd = open_absolute_directory_nofollow(
                archive.parent, handles)
            zip_fd = os.open(
                archive.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=zip_parent_fd)
            handles.callback(os.close, zip_fd)
            if not stat.S_ISREG(os.fstat(zip_fd).st_mode):
                raise GhidraIntegrityError("Release archive is not regular")
            before_zip = _metadata(zip_fd)
            with os.fdopen(os.dup(zip_fd), "rb") as zip_stream:
                sha = _hash_stream(zip_stream)
                if sha != GHIDRA_RELEASE_SHA256:
                    raise GhidraIntegrityError(
                        "Pinned Ghidra release SHA-256 mismatch")
                if before_zip != _metadata(zip_fd):
                    raise GhidraIntegrityError(
                        "Pinned Ghidra ZIP changed while hashing")
                zip_stream.seek(0)
                expected_files: set[str] = set()
                with zipfile.ZipFile(zip_stream, "r") as source:
                    for member in source.infolist():
                        name = member.filename
                        pure = PurePosixPath(name)
                        parts = pure.parts
                        if (not parts or parts[0] != GHIDRA_RELEASE_ROOT
                                or any(part in (".", "..", "") for part in parts)
                                or pure.is_absolute() or "\\" in name
                                or name.rstrip("/") != str(pure).rstrip("/")
                                or member.flag_bits & 0x1):
                            raise GhidraIntegrityError(
                                "Unsafe member in pinned Ghidra archive")
                        if len(parts) == 1:
                            if not member.is_dir():
                                raise GhidraIntegrityError(
                                    "Unexpected archive root file")
                            continue
                        relative = Path(*parts[1:])
                        if member.is_dir():
                            _verify_directory(home_fd, relative)
                            continue
                        mode = (member.external_attr >> 16) & 0o170000
                        if mode not in (0, stat.S_IFREG):
                            raise GhidraIntegrityError(
                                "Non-regular Ghidra ZIP member")
                        key = relative.as_posix()
                        if key in expected_files:
                            raise GhidraIntegrityError(
                                "Duplicate Ghidra archive entry")
                        expected_files.add(key)
                        with source.open(member) as upstream:
                            upstream_hash = _hash_stream(upstream)
                        local_hash = _hash_installed_file(home_fd, relative)
                        if upstream_hash != local_hash:
                            raise GhidraIntegrityError(
                                "Ghidra installed file differs from pinned ZIP")
                if not expected_files:
                    raise GhidraIntegrityError(
                        "Pinned Ghidra archive contains no files")
                if _list_installed_files(home_fd) != expected_files:
                    raise GhidraIntegrityError(
                        "Unlisted or missing Ghidra installation files")
                if before_zip != _metadata(zip_fd):
                    raise GhidraIntegrityError(
                        "Pinned Ghidra ZIP changed during verification")
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile,
            zipfile.LargeZipFile, RuntimeError) as exc:
        if isinstance(exc, GhidraIntegrityError):
            raise
        raise GhidraIntegrityError(
            "Ghidra release integrity could not be verified") from exc
    return {"verified": True, "release_sha256": sha,
            "matched_files": len(expected_files),
            "symlinks_allowed": False, "unexpected_files_allowed": False}
