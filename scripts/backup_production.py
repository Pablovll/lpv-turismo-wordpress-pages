#!/usr/bin/env python3
"""Create and validate a private, local backup before LPV production writes."""
import argparse
import gzip
import io
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .production_common import BACKUPS, ROOT, SSH_ALIAS, WP_ROOT, dump_json, inspect_remote, sha256_bytes
else:
    from production_common import BACKUPS, ROOT, SSH_ALIAS, WP_ROOT, dump_json, inspect_remote, sha256_bytes


def validate_backup(folder):
    folder = Path(folder)
    failures = []
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        return {"status": "BLOQUEADOR", "failures": ["manifest_missing"]}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest.get("files", {}).items():
        path = folder / name
        if not path.is_file() or not path.stat().st_size or sha256_bytes(path.read_bytes()) != expected:
            failures.append(name)
    dump = folder / "database.sql.gz"
    try:
        with gzip.open(dump, "rb") as stream:
            prefix = stream.read(2 * 1024 * 1024)
        if b"CREATE TABLE" not in prefix and b"INSERT INTO" not in prefix:
            failures.append("database_structure_unrecognized")
    except (OSError, EOFError):
        failures.append("database_gzip_invalid")
    for archive in folder.glob("plugin-*.tar.gz"):
        try:
            with tarfile.open(archive, "r:gz") as tar:
                if not tar.getmembers():
                    failures.append(archive.name + ":empty")
        except tarfile.TarError:
            failures.append(archive.name + ":invalid")
    return {"status": "BLOQUEADOR" if failures else "APROVADO", "failures": failures,
            "folder": str(folder), "file_count": len(manifest.get("files", {}))}


def stream_database(path):
    # Hostinger disables proc_open() for PHP, so `wp db export` cannot launch
    # mysqldump. WP-CLI still supplies the live constants; credentials remain
    # only in the remote process environment and the dump streams to stdout.
    remote_script = (
        "set -eu; "
        f"cd {WP_ROOT}; "
        'DB_NAME="$(wp config get DB_NAME --type=constant --no-color)"; '
        'DB_USER="$(wp config get DB_USER --type=constant --no-color)"; '
        'DB_PASSWORD="$(wp config get DB_PASSWORD --type=constant --no-color)"; '
        'DB_HOST="$(wp config get DB_HOST --type=constant --no-color)"; '
        'export MYSQL_PWD="$DB_PASSWORD"; '
        'mysqldump --host="$DB_HOST" --user="$DB_USER" --single-transaction '
        '--quick --skip-lock-tables --no-tablespaces "$DB_NAME"; '
        'unset MYSQL_PWD DB_PASSWORD DB_USER DB_NAME DB_HOST'
    )
    command = ["ssh", SSH_ALIAS, remote_script]
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    with gzip.open(path, "wb", compresslevel=6) as target:
        while True:
            chunk = process.stdout.read(1024 * 1024)
            if not chunk: break
            target.write(chunk)
    stderr = process.stderr.read() if process.stderr else b""
    code = process.wait()
    if code:
        path.unlink(missing_ok=True)
        raise RuntimeError("Database export failed without exposing server output.")
    if stderr and b"Warning" not in stderr:
        raise RuntimeError("Database export reported an error.")


def backup_plugin(folder, slug):
    probe = subprocess.run(["ssh", SSH_ALIAS, f"test -d {WP_ROOT}/wp-content/plugins/{slug}"],
                           cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode:
        return None
    output = folder / f"plugin-{slug}.tar.gz"
    command = ["ssh", SSH_ALIAS,
               f"tar -C {WP_ROOT}/wp-content/plugins -czf - {slug}"]
    with output.open("wb") as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.PIPE)
    if result.returncode:
        output.unlink(missing_ok=True)
        raise RuntimeError(f"Plugin backup failed: {slug}")
    return output


def create_backup(folder=None):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = Path(folder) if folder else BACKUPS / timestamp
    folder.mkdir(parents=True, exist_ok=False)
    state = inspect_remote()
    dump_json(folder / "wordpress-state.json", state)
    (folder / "custom-css.css").write_text(state["custom_css"], encoding="utf-8", newline="")
    pages_dir = folder / "pages"
    pages_dir.mkdir()
    for page_id, page in state["pages"].items():
        (pages_dir / f"{page_id}.html").write_text(page.get("content", ""), encoding="utf-8", newline="")
    dump_json(folder / "page-statuses.json", {
        page_id: page.get("post_status") for page_id, page in state["pages"].items()})
    dump_json(folder / "aioseo-page-metadata.json", {
        page_id: page.get("aioseo", {}) for page_id, page in state["pages"].items()})
    stream_database(folder / "database.sql.gz")
    for slug in ("lpv-page-templates", "lpv-language-seo"):
        backup_plugin(folder, slug)
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[path.relative_to(folder).as_posix()] = sha256_bytes(path.read_bytes())
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "wordpress_root": WP_ROOT, "files": files,
                "database_method": "WP-CLI config constants + remote mysqldump stdout; proc_open unavailable",
                "database_restore": "contingency only; granular rollback is preferred"}
    dump_json(folder / "manifest.json", manifest)
    validation = validate_backup(folder)
    dump_json(folder / "validation.json", validation)
    if validation["status"] != "APROVADO":
        raise RuntimeError("Backup validation failed.")
    return folder, validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    if args.validate:
        report = validate_backup(args.validate)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] == "APROVADO" else 2
    folder, validation = create_backup(args.output_dir)
    print(f"Production backup: {validation['status']}; {folder.name}; {validation['file_count']} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
