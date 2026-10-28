"""Check published GitHub releases and securely install their wheel assets."""

from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPOSITORY = "JessVolet/gbuds-cli"
API_RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases"
API_LATEST_URL = f"{API_RELEASES_URL}/latest"
_VERSION_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:(a|b|rc)(0|[1-9]\d*))?$")
_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
_MAX_WHEEL_BYTES = 50 * 1024 * 1024


class UpdateError(RuntimeError):
    """A release cannot be checked or installed safely."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    url: str
    wheel_url: Optional[str]
    wheel_sha256: Optional[str]


@dataclass(frozen=True)
class UpdateCheck:
    current_version: str
    release: Optional[ReleaseInfo]
    update_available: bool


def parse_version(value: str) -> Optional[tuple[int, int, int, int, int]]:
    """Parse this project's release-tag format into a comparable tuple."""
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        return None
    major, minor, patch, stage, number = match.groups()
    stage_order = {"a": 0, "b": 1, "rc": 2, None: 3}
    return int(major), int(minor), int(patch), stage_order[stage], int(number or 0)


def _is_official_release_url(url: object, tag_name: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.path == f"/{REPOSITORY}/releases/tag/{tag_name}"
    )


def _select_verified_wheel(assets: object, version_string: str, tag_name: str) -> tuple[Optional[str], Optional[str]]:
    expected_name = f"gbuds-{version_string}-py3-none-any.whl"
    if not isinstance(assets, list):
        return None, None

    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") != expected_name:
            continue
        url = asset.get("browser_download_url")
        parsed = urlparse(url) if isinstance(url, str) else None
        expected_path = f"/{REPOSITORY}/releases/download/{tag_name}/{expected_name}"
        if not parsed or parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.path != expected_path:
            continue
        digest = _DIGEST_RE.fullmatch(str(asset.get("digest", "")))
        if not digest:
            return url, None
        return url, digest.group(1).lower()
    return None, None


def select_release(releases: list, include_prerelease: bool = False) -> Optional[ReleaseInfo]:
    """Select the highest valid, published release from GitHub API data."""
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag_name = release.get("tag_name")
        parsed_version = parse_version(tag_name) if isinstance(tag_name, str) else None
        if parsed_version is None or not _is_official_release_url(release.get("html_url"), tag_name):
            continue
        is_prerelease = bool(release.get("prerelease")) or parsed_version[3] < 3
        if is_prerelease and not include_prerelease:
            continue

        version_string = tag_name[1:] if tag_name.startswith("v") else tag_name
        wheel_url, wheel_sha256 = _select_verified_wheel(
            release.get("assets"), version_string, tag_name
        )
        candidates.append((parsed_version, ReleaseInfo(
            version=version_string,
            tag_name=tag_name,
            url=release["html_url"],
            wheel_url=wheel_url,
            wheel_sha256=wheel_sha256,
        )))

    return max(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


def _request_json(url: str):
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "gbuds-update-checker",
        "X-GitHub-Api-Version": "2026-03-10",
    })
    try:
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise UpdateError(f"GitHub release check failed with HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise UpdateError(f"Could not check GitHub releases: {exc}") from exc


def get_latest_release(include_prerelease: bool = False) -> Optional[ReleaseInfo]:
    if include_prerelease:
        releases = _request_json(f"{API_RELEASES_URL}?per_page=100")
        if releases is None:
            return None
        if not isinstance(releases, list):
            raise UpdateError("GitHub returned an invalid release list.")
        return select_release(releases, include_prerelease=True)

    release = _request_json(API_LATEST_URL)
    if release is None:
        return None
    selected = select_release([release], include_prerelease=False)
    if selected is None:
        raise UpdateError("GitHub returned release metadata with an invalid tag or URL.")
    return selected


def check_for_updates(include_prerelease: bool = False) -> UpdateCheck:
    try:
        current = package_version("gbuds")
    except PackageNotFoundError as exc:
        raise UpdateError("Cannot determine the installed Gbuds version. Install Gbuds as a package first.") from exc

    current_key = parse_version(current)
    if current_key is None:
        raise UpdateError(f"Installed version {current!r} is not a supported release version.")
    release = get_latest_release(include_prerelease=include_prerelease)
    update_available = bool(release and parse_version(release.version) > current_key)
    return UpdateCheck(current, release, update_available)


def install_release(release: ReleaseInfo, python_executable: Optional[str] = None) -> None:
    """Install the official wheel into the active virtual environment."""
    if sys.prefix == sys.base_prefix:
        raise UpdateError(
            "Refusing to modify a system Python installation. Run Gbuds inside its pipx or virtual environment."
        )
    if not release.wheel_url:
        raise UpdateError(f"Release {release.tag_name} has no Gbuds wheel. Download it manually from {release.url}.")
    if not release.wheel_sha256:
        raise UpdateError("The release wheel has no GitHub SHA-256 digest; automatic installation was refused.")

    tag_version = parse_version(release.tag_name)
    if (
        not tag_version
        or tag_version != parse_version(release.version)
        or not _is_official_release_url(release.url, release.tag_name)
    ):
        raise UpdateError("Release metadata failed its tag and repository validation.")
    expected_wheel = f"gbuds-{release.version}-py3-none-any.whl"
    wheel_parsed = urlparse(release.wheel_url)
    if (
        wheel_parsed.scheme != "https"
        or wheel_parsed.hostname != "github.com"
        or wheel_parsed.path != f"/{REPOSITORY}/releases/download/{release.tag_name}/{expected_wheel}"
        or not _DIGEST_RE.fullmatch(f"sha256:{release.wheel_sha256}")
    ):
        raise UpdateError("Release wheel metadata failed its URL and digest validation.")

    request = Request(release.wheel_url, headers={"User-Agent": "gbuds-updater"})
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(_MAX_WHEEL_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"Could not download the release wheel: {exc}") from exc

    if len(data) > _MAX_WHEEL_BYTES:
        raise UpdateError("The downloaded wheel exceeds the 50 MiB safety limit.")
    actual_digest = sha256(data).hexdigest()
    if actual_digest != release.wheel_sha256:
        raise UpdateError("The release wheel SHA-256 digest does not match GitHub metadata.")

    with tempfile.TemporaryDirectory(prefix="gbuds-update-") as directory:
        wheel_path = Path(directory) / f"gbuds-{release.version}-py3-none-any.whl"
        wheel_path.write_bytes(data)
        try:
            result = subprocess.run([
                python_executable or sys.executable,
                "-m", "pip", "install", "--no-index", "--no-deps", "--upgrade",
                "--no-input", "--disable-pip-version-check", str(wheel_path),
            ], check=False)
        except OSError as exc:
            raise UpdateError(f"Could not start pip to install the release: {exc}") from exc
        if result.returncode != 0:
            raise UpdateError(f"pip failed to install Gbuds (exit status {result.returncode}).")
