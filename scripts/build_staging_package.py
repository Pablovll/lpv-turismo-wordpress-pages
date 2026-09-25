#!/usr/bin/env python3
"""Assemble reviewed local assets; no network, WordPress writes or deployment."""
import hashlib
import json
import zipfile
from pathlib import Path

from build_wordpress_package import ROOT, load_records, require, validate_html

OUTPUT = ROOT / "publication/stage-6"
STAMP = (2026, 9, 22, 0, 0, 0)


def archive_bytes(files, target):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build():
    _, records = load_records()
    checks = [validate_html(record) for record in records]
    stage4 = ROOT / "publication/stage-4"
    stage5 = ROOT / "publication/stage-5"
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Fail on stale input packages rather than silently mixing releases.
    manifest4 = json.loads((stage4 / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest4.items():
        require(hashlib.sha256((stage4 / name).read_bytes()).hexdigest() == digest,
                f"Stage 4 manifest mismatch: {name}")
    manifest5 = json.loads((stage5 / "manifest.json").read_text(encoding="utf-8"))
    language_zip = stage5 / manifest5["archive"]
    require(hashlib.sha256(language_zip.read_bytes()).hexdigest() == manifest5["archive_sha256"],
            "Stage 5 archive mismatch")
    with zipfile.ZipFile(language_zip) as archive:
        for name, digest in manifest5["files"].items():
            data = archive.read(name)
            require(hashlib.sha256(data).hexdigest() == digest, f"Stage 5 member mismatch: {name}")
            require(data == (ROOT / "wordpress/plugins" / name).read_bytes(),
                    f"Stage 5 stale plugin: {name}")

    files = {}
    for record in records:
        relative = Path(record["source"]).relative_to("pages").as_posix()
        data = (ROOT / record["source"]).read_bytes()
        require(data == (stage4 / "html" / relative).read_bytes(), "Stale Stage 4 HTML")
        files["html/" + relative] = data
    css = (ROOT / "css/lpv-style.css").read_bytes()
    require(css == (stage4 / "css/lpv-style.css").read_bytes()
            == (ROOT / "docs/lpv-css-para-wordpress.css").read_bytes(), "CSS copies differ")
    files["css/lpv-style.css"] = css
    for name, source in {
        "url-map.json": "docs/page-map.json",
        "language-map.json": "docs/stage-4-language-map.json",
        "aioseo-metadata.json": "docs/stage-4-aioseo-metadata.json",
    }.items():
        data = (ROOT / source).read_bytes()
        require(json.loads(data) == json.loads((stage4 / name).read_bytes()), "Stale Stage 4 map")
        # Packaged bytes survive Git newline normalization on Windows.
        files[name] = (stage4 / name).read_bytes()
    for name in ("aioseo-metadata.csv", "PAGE-INVENTORY.md"):
        files[name] = (stage4 / name).read_bytes()

    template = (ROOT / "wordpress/templates/lpv-content-only.html").read_bytes()
    plugin = ROOT / "wordpress/plugins/lpv-page-templates"
    require(template == (plugin / "templates/lpv-content-only.html").read_bytes(),
            "Template copies differ")
    files["wordpress/lpv-content-only.html"] = template
    template_files = {"lpv-page-templates/" + name: (plugin / name).read_bytes()
                      for name in ("lpv-page-templates.php", "README.md", "templates/lpv-content-only.html")}
    template_zip = OUTPUT / "plugins/lpv-page-templates-1.0.1.zip"
    template_zip.parent.mkdir(parents=True, exist_ok=True)
    archive_bytes(template_files, template_zip)
    files["plugins/" + template_zip.name] = template_zip.read_bytes()
    files["plugins/" + language_zip.name] = language_zip.read_bytes()
    files["RUNBOOK.md"] = (ROOT / "docs/stage-6-wordpress-integration.md").read_bytes()
    files["LANGUAGE-PLUGIN.md"] = (ROOT / "wordpress/plugins/lpv-language-seo/README.md").read_bytes()
    files["TEMPLATE-PLUGIN.md"] = (plugin / "README.md").read_bytes()
    files["application-plan.json"] = json_bytes({
        "version": "1.0.1", "date": "2026-09-25", "automatic_deployment": False,
        "target": "Protected staging clone; same IDs and root-relative paths",
        "template": "lpv-page-templates//lpv-content-only",
        "front_page": {"show_on_front": "page", "page_on_front": 7},
        "order": ["backup", "template", "language_plugin", "css", "html", "aioseo",
                  "en_publication_status", "cache_purge", "public_html_audit"],
        "pages": [{key: record[key] for key in ("id", "source", "url", "lang", "status")}
                  for record in records],
        "excluded": ["privacy", "posts", "archives", "search", "404"],
        "hreflang": "Runtime plugin only; do not paste static alternate tags",
        "page_optimization": {
            "provider": "LiteSpeed Cache",
            "scope": "exactly the 22 approved LPV page IDs and paths",
            "global_settings_changed": False,
            "page_cache_preserved": True,
        },
    })
    files["STRUCTURAL-VALIDATION.json"] = json_bytes({
        "scope": "Local fragment validation only; not a WordPress rendering result",
        "pages": checks, "template_copies_identical": True,
        "wordpress_writes": 0, "forms_submitted": 0,
    })
    for name, data in files.items():
        path = OUTPUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    files["manifest.json"] = json_bytes(manifest)
    (OUTPUT / "manifest.json").write_bytes(files["manifest.json"])
    archive = ROOT / "publication/lpv-wordpress-stage-6.zip"
    archive_bytes(files, archive)
    print(f"Prepared {archive}: {len(records)} pages, 2 plugins, {len(files)} files. No deployment.")


if __name__ == "__main__":
    build()
