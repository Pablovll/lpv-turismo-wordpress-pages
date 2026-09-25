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
LITESPEED_PURGE_TIMESTAMP_OPTION = "litespeed.optimize.timestamp_purge_css"


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


def stable_litespeed_configuration(state):
    """Return every monitored LiteSpeed option except the one proven purge marker."""
    explicit = state.get("litespeed_stable_configuration")
    if explicit is not None:
        return explicit
    return {name: digest for name, digest in state.get("litespeed_option_hashes", {}).items()
            if name != LITESPEED_PURGE_TIMESTAMP_OPTION}


def litespeed_purge_timestamp(state):
    operational = state.get("litespeed_operational_state", {}).get(
        LITESPEED_PURGE_TIMESTAMP_OPTION, {})
    value = operational.get("value") if isinstance(operational, dict) else operational
    if value is None:
        return None
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def material_fingerprint(state):
    """State that can change behavior; WordPress modification timestamps are informational."""
    return {
        "home": state.get("home"), "siteurl": state.get("siteurl"),
        "template": state.get("template"), "stylesheet": state.get("stylesheet"),
        "options": state.get("options"), "custom_css_sha256": state.get("custom_css_sha256"),
        "pages": {key: {
            "path": value.get("path"), "post_type": value.get("post_type"),
            "post_name": value.get("post_name"), "post_parent": value.get("post_parent", 0),
            "post_status": value.get("post_status"), "content_sha256": value.get("content_sha256"),
            "aioseo": value.get("aioseo"),
        } for key, value in state.get("pages", {}).items()},
        "plugins": state.get("plugins"), "wp_templates": state.get("wp_templates"),
        "aioseo_option_hashes": state.get("aioseo_option_hashes"),
        "litespeed_stable_configuration": stable_litespeed_configuration(state),
    }


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
