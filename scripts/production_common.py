#!/usr/bin/env python3
"""Shared, non-secret helpers for the controlled LPV production workflow."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "publication/stage-6"
EVIDENCE = ROOT / ".production-evidence"
BACKUPS = ROOT / ".production-private-backup"
SSH_ALIAS = "lpv-prod"
WP_ROOT = "/home/u504635074/domains/lpvturismo.com/public_html"
ORIGIN = "https://lpvturismo.com"
INSPECTOR = ROOT / "wordpress/deploy/inspect-production.php"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def run(command, *, input_bytes=None, check=True, capture=True):
    return subprocess.run(command, cwd=ROOT, input=input_bytes,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None, check=check)


def remote(command, *, input_bytes=None, check=True):
    return run(["ssh", SSH_ALIAS, command], input_bytes=input_bytes, check=check)


def wp(arguments, *, input_bytes=None, check=True):
    command = "cd " + shlex.quote(WP_ROOT) + " && wp " + " ".join(shlex.quote(str(arg)) for arg in arguments)
    return remote(command, input_bytes=input_bytes, check=check)


def inspect_remote():
    result = wp(["eval-file", "-", "--no-color"], input_bytes=INSPECTOR.read_bytes())
    return json.loads(result.stdout.decode("utf-8"))


def load_pages():
    return json.loads((PACKAGE / "language-map.json").read_text(encoding="utf-8"))["pages"]


def load_metadata():
    return {int(row["id"]): row for row in json.loads(
        (PACKAGE / "aioseo-metadata.json").read_text(encoding="utf-8"))}


def approved_content(row):
    return (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_bytes().decode("utf-8")


def dump_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
