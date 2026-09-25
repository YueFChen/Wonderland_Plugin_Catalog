#!/usr/bin/env python3
"""Validate the reviewed static catalog and its public GitHub Release assets."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from stat import S_ISLNK

from catalog_source import CatalogSourceError, load_catalog_plugins

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_RECORDS = ROOT / "catalog" / "v1" / "plugins"
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_PACKAGE_FILES = 10_000
MAX_EXPANDED_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_EXPANDED_FILE_BYTES = 128 * 1024 * 1024
ALLOWED_REDIRECT_HOSTS = {
    "github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}


class CatalogError(ValueError):
    pass


def fail(message: str) -> None:
    raise CatalogError(message)


def is_release_url(url: str, repo: str, plugin_id: str, version: str, architecture: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    expected_file = f"{plugin_id}-{version}-windows-{architecture}.wplug"
    prefix = f"/{repo}/releases/download/"
    tail = parsed.path[len(prefix):] if parsed.path.startswith(prefix) else ""
    release_parts = tail.split("/")
    return (
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and parsed.query == ""
        and parsed.fragment == ""
        and len(release_parts) == 2
        and all(release_parts)
        and release_parts[0] in {version, f"v{version}"}
        and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) and part not in {".", ".."} for part in release_parts)
        and release_parts[1] == expected_file
        and all(part and re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parsed.path.split("/")[1:])
    )


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.redirect_count = 0

    def redirect_request(self, request, response, code, message, headers, new_url):
        self.redirect_count += 1
        parsed = urllib.parse.urlparse(new_url)
        host = (parsed.hostname or "").lower()
        allowed = host in ALLOWED_REDIRECT_HOSTS or (
            host.startswith("github-production-release-asset-")
            and host.endswith(".s3.amazonaws.com")
        )
        if (
            self.redirect_count > 5
            or parsed.scheme != "https"
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or not allowed
        ):
            fail("release asset redirected outside the approved GitHub hosts")
        return super().redirect_request(request, response, code, message, headers, new_url)


def download(url: str, limit: int) -> bytes:
    opener = urllib.request.build_opener(SafeRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "WonderlandAssistant-Catalog-CI"})
    with opener.open(request, timeout=45) as response:
        if response.status != 200:
            fail(f"release asset returned HTTP {response.status}")
        length = response.headers.get("Content-Length")
        if length and int(length) > limit:
            fail("release asset exceeds the 100 MiB limit")
        content = response.read(limit + 1)
        if len(content) > limit:
            fail("release asset exceeds the 100 MiB limit")
        return content


def validate_package(entry: dict) -> None:
    validate_entry_shape(entry)
    repo_url = entry.get("repositoryUrl", "")
    parsed_repo = urllib.parse.urlparse(repo_url)
    repo_parts = parsed_repo.path.strip("/").split("/")
    if (
        parsed_repo.scheme != "https"
        or parsed_repo.netloc != "github.com"
        or len(repo_parts) != 2
        or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in repo_parts)
    ):
        fail(f"{entry.get('id')}: repositoryUrl must be a public GitHub repository URL")
    repo = "/".join(repo_parts)
    plugin_id = entry["id"]
    version = entry["version"]
    architecture = entry["platform"]["architecture"]
    url = entry["downloadUrl"]
    if not is_release_url(url, repo, plugin_id, version, architecture):
        fail(f"{plugin_id}: downloadUrl must target its versioned GitHub Release asset")

    package = download(url, MAX_PACKAGE_BYTES)
    if len(package) != entry["sizeBytes"]:
        fail(f"{plugin_id}: sizeBytes does not match the downloaded package")
    if hashlib.sha256(package).hexdigest() != entry["sha256"]:
        fail(f"{plugin_id}: SHA-256 does not match the downloaded package")

    try:
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            names = archive.namelist()
            infos = archive.infolist()
            if len(infos) > MAX_PACKAGE_FILES or sum(info.file_size for info in infos) > MAX_EXPANDED_PACKAGE_BYTES:
                fail(f"{plugin_id}: package exceeds the expanded file limits")
            if len(names) != len(set(names)):
                fail(f"{plugin_id}: package contains duplicate ZIP paths")
            for info in infos:
                name = info.filename
                path = Path(name)
                posix_parts = name.split("/")
                if (
                    info.file_size > MAX_EXPANDED_FILE_BYTES
                    or path.is_absolute()
                    or name.startswith("/")
                    or re.match(r"^[A-Za-z]:", name)
                    or "\\" in name
                    or ".." in posix_parts
                    or S_ISLNK(info.external_attr >> 16)
                ):
                    fail(f"{plugin_id}: package contains an unsafe ZIP path")
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > 128 * 1024:
                fail(f"{plugin_id}: manifest.json is too large")
            manifest = json.loads(manifest_bytes)
            checksums = json.loads(archive.read("checksums.json"))
            contract_name = manifest["contract"]
            if contract_name not in names:
                fail(f"{plugin_id}: manifest contract file is missing")
            if manifest.get("ui") and manifest["ui"].get("entry") not in names:
                fail(f"{plugin_id}: manifest UI entry is missing")
            if manifest.get("backend", {}).get("entry") not in names:
                fail(f"{plugin_id}: manifest backend entry is missing")
    except (KeyError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        fail(f"{plugin_id}: package is missing a valid manifest, contract, or checksums: {error}")

    expected = {
        "id": entry["id"],
        "name": entry["name"],
        "version": entry["version"],
        "hostCompatibility": entry["hostCompatibility"],
        "uiBridgeCompatibility": entry["uiBridgeCompatibility"],
        "platform": entry["platform"],
        "capabilities": sorted(entry["capabilities"]),
    }
    actual = {key: manifest.get(key) for key in expected}
    actual["capabilities"] = sorted(actual.get("capabilities") or [])
    actual["uiBridgeCompatibility"] = manifest.get("ui", {}).get("bridgeCompatibility") if manifest.get("ui") else None
    if actual != expected:
        fail(f"{plugin_id}: catalog metadata does not match manifest.json")
    if manifest.get("manifestVersion") != 2:
        fail(f"{plugin_id}: only plugin manifest version 2 is supported")
    if checksums.get("algorithm") != "sha256" or not isinstance(checksums.get("files"), list):
        fail(f"{plugin_id}: checksums.json is invalid")
    checksum_map = {
        item.get("path"): item.get("sha256")
        for item in checksums["files"]
        if isinstance(item, dict)
    }
    package_files = {name for name in names if not name.endswith("/") and name != "checksums.json"}
    if set(checksum_map) != package_files or len(checksum_map) != len(checksums["files"]):
        fail(f"{plugin_id}: checksums.json does not cover the package files exactly")
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        for name, digest in checksum_map.items():
            if not isinstance(digest, str) or hashlib.sha256(archive.read(name)).hexdigest() != digest:
                fail(f"{plugin_id}: package internal checksum failed for {name}")


def validate_entry_shape(entry: dict) -> None:
    required = {
        "id", "name", "description", "author", "repositoryUrl", "version", "downloadUrl",
        "sha256", "sizeBytes", "hostCompatibility", "uiBridgeCompatibility", "platform", "capabilities",
    }
    allowed = required | {"releaseNotesUrl"}
    if not isinstance(entry, dict) or not required.issubset(entry) or not set(entry).issubset(allowed):
        fail("plugin entry has missing or unknown fields")
    string_limits = {"id": 64, "name": 120, "description": 2000, "author": 120,
                     "repositoryUrl": 500, "version": 64, "downloadUrl": 2000, "sha256": 64}
    for key, limit in string_limits.items():
        if not isinstance(entry[key], str) or len(entry[key]) > limit:
            fail(f"{entry.get('id', '?')}: {key} must be a string of at most {limit} characters")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", entry["id"]):
        fail("plugin ID is invalid")
    semver = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?$"
    if not re.fullmatch(semver, entry["version"]):
        fail(f"{entry['id']}: version must be a stable or prerelease SemVer without build metadata")
    semver_key(entry["version"])
    if not entry["name"].strip() or not entry["author"].strip():
        fail(f"{entry['id']}: name and author cannot be empty")
    if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
        fail(f"{entry['id']}: sha256 must be lowercase hexadecimal")
    if not isinstance(entry["sizeBytes"], int) or isinstance(entry["sizeBytes"], bool) or not 1 <= entry["sizeBytes"] <= MAX_PACKAGE_BYTES:
        fail(f"{entry['id']}: sizeBytes must be between 1 and 100 MiB")
    if not isinstance(entry["capabilities"], list) or len(set(entry["capabilities"])) != len(entry["capabilities"]):
        fail(f"{entry['id']}: capabilities must be a unique list")
    if any(not isinstance(cap, str) or not cap.strip() or len(cap) > 128 for cap in entry["capabilities"]):
        fail(f"{entry['id']}: capability names are invalid")
    host = entry["hostCompatibility"]
    platform = entry["platform"]
    if not isinstance(host, dict) or set(host) != {"minCoreVersion", "maxCoreVersionExclusive", "protocol"}:
        fail(f"{entry['id']}: hostCompatibility fields are invalid")
    if not isinstance(host["protocol"], dict) or set(host["protocol"]) != {"minVersion", "maxVersionExclusive"}:
        fail(f"{entry['id']}: protocol compatibility fields are invalid")
    bounds = [
        host["minCoreVersion"],
        host["maxCoreVersionExclusive"],
        host["protocol"]["minVersion"],
        host["protocol"]["maxVersionExclusive"],
    ]
    for value in bounds:
        if not isinstance(value, str) or not re.fullmatch(semver, value):
            fail(f"{entry['id']}: compatibility bounds must be valid SemVer")
        semver_key(value)
    if semver_key(bounds[0]) >= semver_key(bounds[1]) or semver_key(bounds[2]) >= semver_key(bounds[3]):
        fail(f"{entry['id']}: compatibility ranges must have increasing bounds")
    ui_compatibility = entry["uiBridgeCompatibility"]
    if ui_compatibility is not None:
        if not isinstance(ui_compatibility, dict) or set(ui_compatibility) != {"minVersion", "maxVersionExclusive"}:
            fail(f"{entry['id']}: UI bridge compatibility fields are invalid")
        ui_min = ui_compatibility["minVersion"]
        ui_max = ui_compatibility["maxVersionExclusive"]
        semver_key(ui_min)
        semver_key(ui_max)
        if semver_key(ui_min) >= semver_key(ui_max):
            fail(f"{entry['id']}: UI bridge compatibility range must have increasing bounds")
    if not isinstance(platform, dict) or set(platform) != {"os", "architecture", "abi"}:
        fail(f"{entry['id']}: platform fields are invalid")
    if platform != {"os": "windows", "architecture": platform.get("architecture"), "abi": "msvc"} or platform["architecture"] not in {"x86_64", "aarch64"}:
        fail(f"{entry['id']}: unsupported platform")
    if "releaseNotesUrl" in entry and entry["releaseNotesUrl"] is not None:
        parsed = urllib.parse.urlparse(entry["releaseNotesUrl"])
        expected_prefix = f"https://github.com/{repo_path(entry['repositoryUrl'])}/releases/tag/"
        tag = entry["releaseNotesUrl"].removeprefix(expected_prefix)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "github.com"
            or not entry["releaseNotesUrl"].startswith(expected_prefix)
            or not tag
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", tag)
            or parsed.query
            or parsed.fragment
        ):
            fail(f"{entry['id']}: releaseNotesUrl must be an HTTPS GitHub URL")


def repo_path(repository_url: str) -> str:
    parsed = urllib.parse.urlparse(repository_url)
    path = parsed.path.strip("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or len(path.split("/")) != 2
        or parsed.query
        or parsed.fragment
    ):
        fail("repositoryUrl must be an HTTPS GitHub owner/repository URL")
    return path


def semver_key(value: str) -> tuple:
    match = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?", value)
    if not match:
        fail(f"invalid SemVer: {value}")
    prerelease = match.group(4)
    if prerelease is None:
        pre_key = (1,)
    else:
        identifiers = prerelease.split(".")
        if any(not item or (item.isdigit() and len(item) > 1 and item.startswith("0")) for item in identifiers):
            fail(f"invalid SemVer prerelease: {value}")
        pre_key = (0, tuple((0, int(item)) if item.isdigit() else (1, item) for item in identifiers))
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), pre_key


def main() -> int:
    try:
        entries = load_catalog_plugins(PLUGIN_RECORDS)
        for entry in entries:
            validate_package(entry)
        print(f"Validated {len(entries)} plugin catalog entr{'y' if len(entries) == 1 else 'ies'}.")
        return 0
    except (CatalogError, CatalogSourceError, OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        print(f"Plugin catalog validation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
