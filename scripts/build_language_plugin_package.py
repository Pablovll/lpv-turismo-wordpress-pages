#!/usr/bin/env python3
"""Package only the reviewed plugin files. No WordPress connection or activation."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "wordpress/plugins/lpv-language-seo"
OUTPUT = ROOT / "publication/stage-5"
FILES = ("lpv-language-seo.php", "README.md")


def build():
    source = (PLUGIN / FILES[0]).read_text(encoding="utf-8")
    version = re.search(r"^ \* Version: ([0-9.]+)$", source, re.MULTILINE).group(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    archive = OUTPUT / f"lpv-language-seo-{version}.zip"
    hashes = {}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name in FILES:
            data = (PLUGIN / name).read_bytes()
            member = "lpv-language-seo/" + name
            info = zipfile.ZipInfo(member, date_time=(2026, 9, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(info, data)
            hashes[member] = hashlib.sha256(data).hexdigest()
    manifest = {
        "version": version,
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": hashes,
        "installation": "Manual only. Not installed or activated on WordPress.",
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {archive} ({len(FILES)} files, no automatic deployment)")


if __name__ == "__main__":
    build()
