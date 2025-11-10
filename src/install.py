#!/usr/bin/env python3
"""Installer for codexu compatible with `curl ... | python -` usage."""

from __future__ import annotations

import platform
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CODEXU_SOURCE_URL = (
    "https://raw.githubusercontent.com/divinity76/codexu/refs/heads/main/src/codexu.py"
)
USER_AGENT = "codexu-installer/1.0 (+https://github.com/divinity76/codexu)"


class InstallerError(RuntimeError):
    """Raised when the installer cannot complete."""


def main() -> int:
    try:
        codex_binary = resolve_codex_binary()
        target_dir = codex_binary.parent
        print(f"Detected codex binary at {codex_binary}")

        codexu_bytes = download_codexu()
        if is_windows():
            install_windows(codexu_bytes, target_dir)
        else:
            install_unix(codexu_bytes, target_dir)

        print("codexu installation complete.")
        return 0
    except InstallerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def resolve_codex_binary() -> Path:
    """Return the path to the codex executable as exposed on PATH."""
    location = shutil.which("codex")
    if not location:
        raise InstallerError(
            "codex executable not found in PATH. Please install codex first."
        )
    return Path(location)


def download_codexu() -> bytes:
    """Download codexu.py bytes from the canonical source."""
    print(f"Fetching codexu from {CODEXU_SOURCE_URL}")
    request = Request(
        CODEXU_SOURCE_URL,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except HTTPError as exc:
        raise InstallerError(
            f"Failed to download codexu (HTTP {exc.code}): {exc.reason}"
        ) from exc
    except URLError as exc:
        raise InstallerError(f"Failed to download codexu: {exc.reason}") from exc


def install_unix(codexu_bytes: bytes, target_dir: Path) -> None:
    """Install codexu alongside the codex binary on Unix systems."""
    target_path = target_dir / "codexu"
    print(f"Installing codexu script to {target_path}")
    stage_atomic_write(target_path, codexu_bytes)
    current_mode = target_path.stat().st_mode
    target_path.chmod(current_mode | 0o111)


def install_windows(codexu_bytes: bytes, target_dir: Path) -> None:
    """Install codexu alongside the codex binary on Windows systems."""
    codexu_py = target_dir / "codexu.py"
    codexu_bat = target_dir / "codexu.bat"

    print(f"Installing codexu.py to {codexu_py}")
    stage_atomic_write(codexu_py, codexu_bytes)

    batch_contents = (
        "@echo off\r\n"
        "setlocal\r\n"
        "set CODExU_PY=\"%~dp0codexu.py\"\r\n"
        "where python >nul 2>&1\r\n"
        "if %errorlevel%==0 (\r\n"
        "    python %CODExU_PY% %*\r\n"
        "    goto :eof\r\n"
        ")\r\n"
        "where python3 >nul 2>&1\r\n"
        "if %errorlevel%==0 (\r\n"
        "    python3 %CODExU_PY% %*\r\n"
        "    goto :eof\r\n"
        ")\r\n"
        "echo Neither python nor python3 was found in PATH.>&2\r\n"
        "exit /b 1\r\n"
    ).encode("utf-8")
    print(f"Installing launcher batch file to {codexu_bat}")
    stage_atomic_write(codexu_bat, batch_contents)


def stage_atomic_write(target_path: Path, data: bytes) -> None:
    """Write data to target_path via a temporary file for safety."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False, dir=target_path.parent, prefix=f".{target_path.name}."
    ) as tmp_file:
        tmp_file.write(data)
        tmp_path = Path(tmp_file.name)

    try:
        tmp_path.replace(target_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise InstallerError(f"Failed to write {target_path}: {exc}") from exc


def is_windows() -> bool:
    """Return True if running on Windows."""
    return platform.system().lower().startswith("win")


if __name__ == "__main__":
    sys.exit(main())
