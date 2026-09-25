#!/usr/bin/env python3
"""Build the small, versioned static site artifact for GitHub Pages."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "catalog"
DESTINATION = ROOT / "_site"
VERSIONED_DESTINATION = DESTINATION / "catalog" / "v1"

DESTINATION.mkdir(parents=True, exist_ok=True)
VERSIONED_DESTINATION.mkdir(parents=True, exist_ok=True)
shutil.copyfile(SOURCE / "index.html", DESTINATION / "index.html")
shutil.copyfile(SOURCE / "v1" / "index.schema.json", VERSIONED_DESTINATION / "index.schema.json")
index = json.loads((SOURCE / "v1" / "index.json").read_text(encoding="utf-8"))
index["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
(VERSIONED_DESTINATION / "index.json").write_text(
    json.dumps(index, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
(DESTINATION / ".nojekyll").touch()
