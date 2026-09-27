#!/usr/bin/env python3
"""Load the reviewed per-plugin identity registrations used to build the public index."""

import json
import re
from pathlib import Path

MAX_CATALOG_PLUGINS = 500
PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class CatalogSourceError(ValueError):
    pass


def load_catalog_plugins(directory: Path) -> list[dict]:
    """Load direct JSON children, enforce ``<plugin-id>.json``, and sort by ID."""
    if directory.is_symlink() or not directory.is_dir():
        raise CatalogSourceError(f"plugin record directory is missing or unsafe: {directory}")

    entries = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json":
            raise CatalogSourceError(f"unexpected item in plugin record directory: {path.name}")
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CatalogSourceError(f"{path.name}: invalid UTF-8 JSON: {error}") from error
        if not isinstance(entry, dict):
            raise CatalogSourceError(f"{path.name}: plugin record must be a JSON object")

        plugin_id = entry.get("id")
        if not isinstance(plugin_id, str) or not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
            raise CatalogSourceError(f"{path.name}: plugin id is invalid")
        if path.name != f"{plugin_id}.json":
            raise CatalogSourceError(f"{path.name}: filename must match plugin id {plugin_id!r}")
        entries.append(entry)

    if len(entries) > MAX_CATALOG_PLUGINS:
        raise CatalogSourceError(f"catalog contains more than {MAX_CATALOG_PLUGINS} plugin records")
    plugin_ids = [entry["id"] for entry in entries]
    if len(plugin_ids) != len(set(plugin_ids)):
        raise CatalogSourceError("plugin record IDs must be unique")
    return sorted(entries, key=lambda entry: entry["id"])
