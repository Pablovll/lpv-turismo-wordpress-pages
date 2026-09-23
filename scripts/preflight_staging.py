#!/usr/bin/env python3
"""Offline package integrity and heuristic sensitive-data preflight. No network."""
import argparse
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "publication/stage-6"
PATTERNS = {
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "access_token": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b",
    "credential_assignment": r'''(?i)(?:password|api[_-]?key|access[_-]?token|secret)\s*[=:]\s*["']([A-Za-z0-9/+_=.-]{12,})["']''',
    "wp_application_password": r"(?i)application\s+password\s*:\s*(?:[A-Za-z0-9]{4} ){5}[A-Za-z0-9]{4}\b",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_preflight(folder=PACKAGE, archive=None):
    archive = archive or folder.parent / "lpv-wordpress-stage-6.zip"
    manifest = json.loads((folder / "manifest.json").read_bytes())
    failures = []
    for name, expected in manifest.items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file() or digest(path.read_bytes()) != expected:
            failures.append(name)
    with zipfile.ZipFile(archive) as zipped:
        if len(zipped.namelist()) != len(manifest) + 1 or set(zipped.namelist()) != {*manifest, "manifest.json"}:
            failures.append("archive_inventory")
        for name in {*manifest, "manifest.json"}:
            if name not in zipped.namelist() or zipped.read(name) != (folder / name).read_bytes():
                failures.append("archive:" + name)
    required = {"plugins/lpv-page-templates-1.0.0.zip", "plugins/lpv-language-seo-1.0.0.zip",
                "css/lpv-style.css", "aioseo-metadata.json", "aioseo-metadata.csv",
                "url-map.json", "language-map.json", "wordpress/lpv-content-only.html"}
    failures.extend(sorted(required - manifest.keys()))
    rows = json.loads((folder / "language-map.json").read_bytes())["pages"]
    html = {name for name in manifest if name.startswith("html/")}
    expected_html = {"html/" + row["source"].removeprefix("pages/") for row in rows}
    if len(rows) != 22 or html != expected_html:
        failures.append("22_html_inventory")
    return {"status": "BLOQUEADOR" if failures else "APROVADO", "manifest_files": len(manifest),
            "html_files": len(html), "archive_sha256": digest(archive.read_bytes()), "failures": failures}


def sensitive_indicators(name, data, depth=0):
    """Return categories/locations only, never matched values or source lines."""
    findings = []
    if re.search(r"(?i)(?:^|/)(?:\.env(?:\..*)?|wp-config\.php|[^/]*\.(?:sql(?:\.gz)?|wpress|pem|key))$", name):
        findings.append({"file": name, "rule": "sensitive_filename"})
    if data.startswith(b"PK\x03\x04"):
        if depth >= 3:
            return findings + [{"file": name, "rule": "archive_depth_unverified"}]
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > 64 * 1024 * 1024:
                    return findings + [{"file": name, "rule": "archive_size_unverified"}]
                for entry in archive.infolist():
                    if not entry.is_dir():
                        findings.extend(sensitive_indicators(name + "!/" + entry.filename, archive.read(entry), depth + 1))
        except (zipfile.BadZipFile, RuntimeError):
            findings.append({"file": name, "rule": "unreadable_archive"})
        return findings
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        return findings
    for rule, pattern in PATTERNS.items():
        if re.search(pattern, text):
            findings.append({"file": name, "rule": rule})
    emails = set(re.findall(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
    for address in emails:
        approved = {"info@lpvturismo.com", "seuemail@exemplo.com", "tuemail@ejemplo.com"}
        domain = address.rsplit("@", 1)[1].lower()
        example = domain in {"example.com", "example.test"} or domain.endswith((".example.com", ".example.test"))
        if address.lower() not in approved and not example:
            findings.append({"file": name, "rule": "email_requires_review"})
            break
    return findings


def git(*args, data=None):
    return subprocess.run(["git", *args], cwd=ROOT, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def repository_scan():
    paths = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    findings = []
    binary_files = []
    for name in filter(None, paths):
        data = (ROOT / name).read_bytes()
        findings.extend(sensitive_indicators(name, data))
        if not data.startswith(b"PK\x03\x04"):
            try:
                data.decode("utf-8")
            except UnicodeError:
                binary_files.append(name)
    objects = git("rev-list", "--objects", "--all").splitlines()
    names = {line.split(b" ", 1)[0]: line.split(b" ", 1)[-1].decode("utf-8", "replace") for line in objects}
    index = git("cat-file", "--batch-check", data=b"\n".join(names) + b"\n")
    blobs = [line.split()[0] for line in index.splitlines() if line.split()[1] == b"blob"]
    stream = io.BytesIO(git("cat-file", "--batch", data=b"\n".join(blobs) + b"\n"))
    for _ in blobs:
        oid, _, size = stream.readline().split()
        data = stream.read(int(size))
        stream.read(1)
        findings.extend(sensitive_indicators("history:" + names[oid], data))
    # Deduplicate repeated package/history occurrences without logging values.
    findings = [dict(file=file, rule=rule) for file, rule in sorted({(f["file"], f["rule"]) for f in findings})]
    return {"status": "BLOQUEADOR" if findings else "APROVADO", "findings": findings,
            "working_files": len(list(filter(None, paths))), "reachable_history_blobs": len(blobs),
            "scope": "Heuristic text/filename/ZIP scan; reachable local Git history and working files. Not a proof of no PII.",
            "binary_visual_review": "NAO TESTADO", "binary_files": binary_files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"git_status": git("status", "--short", "--branch").decode().splitlines(),
              "package": package_preflight(), "sensitive_data": repository_scan(),
              "staging": "PENDENTE", "network_requests": 0}
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 2 if any(report[key]["status"] == "BLOQUEADOR" for key in ("package", "sensitive_data")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
