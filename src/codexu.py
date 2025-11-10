#!/usr/bin/env python3
"""Utility to keep Codex aligned with the latest GitHub release."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LATEST_RELEASE_URL = "https://github.com/openai/codex/releases/latest"
GITHUB_API_RELEASE_TMPL = (
    "https://api.github.com/repos/openai/codex/releases/tags/{tag}"
)
USER_AGENT = "codexu/1.0 (+https://github.com/openai/codex)"

OS_KEYWORDS = {
    "windows": ("windows", "msvc", "win"),
    "darwin": ("darwin", "mac", "osx"),
    "linux": ("linux",),
}
ARCH_KEYWORDS = {
    "x86_64": ("x86_64", "amd64"),
    "arm64": ("arm64", "aarch64"),
}
NON_CLI_KEYWORDS = ("responses", "proxy", "sdk", "npm")
TAR_SUFFIX_PATTERNS = (
    (".tar", ".gz"),
    (".tar", ".xz"),
    (".tar", ".bz2"),
    (".tar", ".zst"),
    (".tar",),
    (".tgz",),
    (".tbz2",),
    (".txz",),
)


class CodexUError(RuntimeError):
    """Raised when the Codex updater encounters an unrecoverable problem."""


class InstallMethod(Enum):
    HOME_BREW = "homebrew"
    NPM = "npm"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str


def normalize_version(raw: str | None) -> str | None:
    """Extract a comparable version token, dropping an optional leading 'v'."""
    if not raw:
        return None

    raw = raw.strip()
    match = re.search(r"v?(\d+(?:\.\d+)*([\-\w.]+)?)", raw, re.IGNORECASE)
    version = match.group(0) if match else raw
    return version[1:] if version.lower().startswith("v") else version


def get_installed_version() -> str:
    """Return the locally installed Codex version string."""
    try:
        result = subprocess.run(
            ["codex", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CodexUError("codex executable not found in PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "unknown error"
        raise CodexUError(f"codex --version failed: {stderr}") from exc

    version = normalize_version(result.stdout) or normalize_version(result.stderr)
    if not version:
        raise CodexUError("Unable to parse codex --version output")
    return version


def get_latest_release_info() -> ReleaseInfo:
    """Resolve GitHub's latest release redirect and extract the tag + version."""
    try:
        with urlopen(LATEST_RELEASE_URL, timeout=10) as response:
            final_url = response.geturl()
    except OSError as exc:
        raise CodexUError(f"Failed to query GitHub releases: {exc}") from exc

    path = urlparse(final_url).path.rstrip("/")
    tag = path.split("/")[-1] if path else ""
    version = normalize_version(tag)
    if not version or not tag:
        raise CodexUError(
            f"Unable to determine version from redirect URL: {final_url}"
        )
    return ReleaseInfo(version=version, tag=tag)


def start_codex() -> int:
    """Launch Codex and return its exit code."""
    return subprocess.call(["codex"])


def detect_install_method() -> InstallMethod:
    """Infer how Codex is installed on the system."""
    if _is_homebrew_install():
        return InstallMethod.HOME_BREW
    if _is_npm_install():
        return InstallMethod.NPM
    return InstallMethod.CUSTOM


def _is_homebrew_install() -> bool:
    """Return True if Codex appears to be installed via Homebrew."""
    if shutil.which("brew") is None:
        return False

    result = subprocess.run(
        ["brew", "list", "--cask", "codex"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _is_npm_install() -> bool:
    """Return True if Codex appears to be installed via npm."""
    if shutil.which("npm") is None:
        return False

    result = subprocess.run(
        ["npm", "list", "-g", "@openai/codex", "--depth=0"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def run_command(command: list[str]) -> None:
    """Execute a shell command, surfacing any failure."""
    print(f"Running: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise CodexUError(
            f"Command {' '.join(command)} failed with exit code {exc.returncode}"
        ) from exc


def update_codex(installed: str, release: ReleaseInfo) -> None:
    """Update Codex using Homebrew, npm, or fallback download."""
    method = detect_install_method()
    print(
        f"Updating Codex from {installed} -> {release.version} "
        f"using {method.value} workflow."
    )

    if method is InstallMethod.HOME_BREW:
        run_command(["brew", "upgrade", "--cask", "codex"])
        return

    if method is InstallMethod.NPM:
        run_command(["npm", "update", "-g", "@openai/codex"])
        return

    install_custom_release(release)


def install_custom_release(release: ReleaseInfo) -> None:
    """Download, extract, and replace the Codex binary for custom installs."""
    codex_path = get_codex_binary_path()
    metadata = fetch_release_metadata(release.tag)
    assets = metadata.get("assets", [])
    asset = select_asset_for_current_platform(assets)
    if not asset:
        raise CodexUError(
            f"No compatible asset found for release {release.tag}. "
            "Please download the appropriate file manually."
        )

    download_url = asset.get("browser_download_url")
    asset_name = asset.get("name", "codex-release")
    if not download_url:
        raise CodexUError("Release asset is missing a download URL.")

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        archive_path = tmpdir / asset_name
        print(f"Downloading {asset_name} to {archive_path} ...")
        download_file(download_url, archive_path)

        extracted_root = extract_archive(archive_path, tmpdir)
        binary_candidate: Path | None
        if extracted_root.is_dir():
            binary_candidate = locate_codex_binary(extracted_root)
        elif is_codex_binary_name(extracted_root.name):
            binary_candidate = extracted_root
        else:
            binary_candidate = None

        if binary_candidate is None:
            raise CodexUError(
                "Unable to locate Codex executable inside downloaded artifact."
            )

        stage_and_replace_binary(binary_candidate, codex_path)


def get_codex_binary_path() -> Path:
    """Return the filesystem path of the current codex executable."""
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise CodexUError("codex executable not found in PATH")
    return Path(codex_bin).resolve()


def download_file(url: str, dest: Path) -> None:
    """Download a URL to dest, overwriting any existing file."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response, dest.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    except OSError as exc:
        raise CodexUError(f"Failed to download {url}: {exc}") from exc


def extract_archive(archive_path: Path, temp_dir: Path) -> Path:
    """Extract the archive if needed, returning the root of extracted files."""
    suffixes = [s.lower() for s in archive_path.suffixes]
    if suffixes[-1:] == [".zip"]:
        destination = temp_dir / "extracted"
        destination.mkdir(exist_ok=True)
        try:
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(destination)
        except (zipfile.BadZipFile, OSError) as exc:
            raise CodexUError(f"Failed to extract zip archive: {exc}") from exc
        return destination

    for pattern in TAR_SUFFIX_PATTERNS:
        if suffixes[-len(pattern):] == list(pattern):
            destination = temp_dir / "extracted"
            destination.mkdir(exist_ok=True)
            try:
                with tarfile.open(archive_path) as tf:
                    tf.extractall(destination)
            except (tarfile.TarError, OSError) as exc:
                raise CodexUError(f"Failed to extract tar archive: {exc}") from exc
            return destination

    return archive_path


def locate_codex_binary(root: Path) -> Path | None:
    """Search for a codex executable inside the extracted directory."""
    if root.is_file() and is_codex_binary_name(root.name):
        return root

    candidates: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and is_codex_binary_name(path.name):
            candidates.append(path)

    if not candidates:
        return None

    if platform.system().lower().startswith("win"):
        for candidate in candidates:
            if candidate.suffix.lower() == ".exe":
                return candidate

    return candidates[0]


def stage_and_replace_binary(source_binary: Path, codex_path: Path) -> None:
    """Stage the new binary beside the existing one and replace it atomically."""
    target_dir = codex_path.parent
    temp_target = target_dir / f".{codex_path.name}.new"
    backup_target = target_dir / f"{codex_path.name}.bak"

    shutil.copy2(source_binary, temp_target)
    make_executable(temp_target)

    if backup_target.exists():
        backup_target.unlink()

    if codex_path.exists():
        print(f"Creating backup at {backup_target}")
        codex_path.replace(backup_target)

    try:
        temp_target.replace(codex_path)
    except OSError as exc:
        if not codex_path.exists() and backup_target.exists():
            backup_target.replace(codex_path)
        raise CodexUError(
            f"Failed to place new binary at {codex_path}: {exc}"
        ) from exc

    print(f"Installed new Codex binary to {codex_path}")


def make_executable(path: Path) -> None:
    """Ensure the copied binary is marked executable on POSIX systems."""
    if os.name == "nt":
        return
    current_mode = path.stat().st_mode
    path.chmod(current_mode | 0o111)


def fetch_release_metadata(tag: str) -> dict:
    """Fetch release metadata for the specific GitHub tag."""
    url = GITHUB_API_RELEASE_TMPL.format(tag=tag)
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = response.read()
    except HTTPError as exc:
        raise CodexUError(
            f"Failed to fetch release data for {tag}: HTTP {exc.code}"
        ) from exc
    except OSError as exc:
        raise CodexUError(f"Failed to fetch release data for {tag}: {exc}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CodexUError("Received invalid JSON from GitHub releases API") from exc


def select_asset_for_current_platform(assets: list[dict]) -> dict | None:
    """Pick the best matching asset for the current OS/architecture."""
    os_key = normalize_os(platform.system())
    arch_key = normalize_arch(platform.machine())

    filtered_assets = _filter_cli_assets(assets)
    candidate_groups = [
        _filter_by_os_and_arch(filtered_assets, os_key, arch_key),
        _filter_by_os_and_arch(assets, os_key, arch_key),
        _filter_by_os(filtered_assets, os_key),
        _filter_by_os(assets, os_key),
        filtered_assets,
        assets,
    ]

    for group in candidate_groups:
        if group:
            return _choose_best_packaging(group, os_key)
    return None


def _filter_cli_assets(assets: list[dict]) -> list[dict]:
    result: list[dict] = []
    for asset in assets:
        name = asset.get("name", "").lower()
        if not name:
            continue
        if any(keyword in name for keyword in NON_CLI_KEYWORDS):
            continue
        result.append(asset)
    return result


def _filter_by_os_and_arch(
    assets: list[dict], os_key: str | None, arch_key: str | None
) -> list[dict]:
    return [
        asset
        for asset in assets
        if _matches_os(asset, os_key) and _matches_arch(asset, arch_key)
    ]


def _filter_by_os(assets: list[dict], os_key: str | None) -> list[dict]:
    return [asset for asset in assets if _matches_os(asset, os_key)]


def _matches_os(asset: dict, os_key: str | None) -> bool:
    if not os_key:
        return True
    name = asset.get("name", "").lower()
    return any(keyword in name for keyword in OS_KEYWORDS.get(os_key, ()))


def _matches_arch(asset: dict, arch_key: str | None) -> bool:
    if not arch_key:
        return True
    name = asset.get("name", "").lower()
    return any(keyword in name for keyword in ARCH_KEYWORDS.get(arch_key, ()))


def _choose_best_packaging(assets: list[dict], os_key: str | None) -> dict:
    preferences = {
        "windows": [".zip", ".tar.gz", ".tar", ".zst"],
        "darwin": [".tar.gz", ".zip", ".tar", ".zst"],
        "linux": [".tar.gz", ".tar", ".zst", ".zip"],
        None: [".zip", ".tar.gz", ".tar", ".zst"],
    }
    preferred_order = preferences.get(os_key, preferences[None])

    def score(asset: dict) -> int:
        name = asset.get("name", "").lower()
        for idx, ext in enumerate(preferred_order):
            if name.endswith(ext):
                return len(preferred_order) - idx
        return 0

    best_asset = max(assets, key=score)
    return best_asset



def is_codex_binary_name(name: str) -> bool:
    lower = name.lower()
    stripped = lower[:-4] if lower.endswith('.exe') else lower
    if any(keyword in stripped for keyword in NON_CLI_KEYWORDS):
        return False
    return stripped == 'codex' or stripped.startswith('codex-')


def normalize_os(raw: str | None) -> str | None:
    """Map platform.system() output to canonical keys."""
    if not raw:
        return None

    raw = raw.lower()
    if raw.startswith("win"):
        return "windows"
    if raw.startswith("darwin"):
        return "darwin"
    if raw.startswith("linux"):
        return "linux"
    return None


def normalize_arch(raw: str | None) -> str | None:
    """Map platform.machine() output to canonical architecture keys."""
    if not raw:
        return None

    raw = raw.lower()
    if raw in ("x86_64", "amd64"):
        return "x86_64"
    if raw in ("arm64", "aarch64"):
        return "arm64"
    return raw


def main() -> int:
    try:
        installed_version = get_installed_version()
        release = get_latest_release_info()
    except CodexUError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if installed_version == release.version:
        print(f"Codex is up to date ({installed_version}). Starting Codex...")
        return start_codex()

    try:
        update_codex(installed_version, release)
    except CodexUError as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
