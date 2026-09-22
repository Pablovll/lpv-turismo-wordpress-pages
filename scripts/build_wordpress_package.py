#!/usr/bin/env python3
"""Build a local review package. No network, publishing or form submission."""
import csv
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "publication/stage-4"
LANGUAGES = {"pt": "pt-BR", "es": "es", "en": "en"}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class BalancedHTML(HTMLParser):
    """Check explicit tag balance in our fragments, without browser repairs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"Unexpected </{tag}> at {self.getpos()}")
        else:
            self.stack.pop()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_metadata():
    document = (ROOT / "docs/stage-3-quality-audit.md").read_text(encoding="utf-8")
    rows = csv.reader(document.splitlines(), delimiter="|", quoting=csv.QUOTE_NONE)
    metadata = {}
    for row in rows:
        if len(row) == 5 and row[1].strip().startswith("`/"):
            path, title, description = (cell.strip().strip("`") for cell in row[1:4])
            require(path not in metadata, f"Duplicate metadata: {path}")
            metadata[path] = {"title": title, "description": description}
    require(len(metadata) == 22, "Expected 22 metadata rows in the stage 3 table")
    return metadata


def load_records():
    page_map = json.loads((ROOT / "docs/page-map.json").read_text(encoding="utf-8"))
    metadata = read_metadata()
    records = []
    for language, pages in page_map["pages"].items():
        for page in pages.values():
            alternatives = {}
            fallbacks = {}
            absent = []
            for key, equivalent in page_map["language_equivalents"][page["family"]].items():
                if isinstance(equivalent, dict) and equivalent["fallback"]:
                    absent.append(LANGUAGES[key])
                    fallbacks[LANGUAGES[key]] = equivalent["url"]
                else:
                    path = equivalent["url"] if isinstance(equivalent, dict) else equivalent
                    alternatives[LANGUAGES[key]] = page_map["site"] + path
            alternatives["x-default"] = alternatives["pt-BR"]
            require(page["lang"] == LANGUAGES[language], f"Invalid lang for {page['id']}")
            records.append({
                **page,
                "canonical": page_map["site"] + page["url"],
                "alternates": alternatives,
                "missing_direct_equivalents": absent,
                "navigation_fallbacks_not_hreflang": fallbacks,
                **metadata[page["url"]],
            })
    require({r["url"] for r in records} == set(metadata), "Metadata/page-map mismatch")
    validate_records(records)
    return page_map, records


def validate_records(records):
    require(len(records) == 22, "Expected 22 content pages")
    require(len({r["id"] for r in records}) == 22, "Duplicate page IDs")
    require(len({r["source"] for r in records}) == 22, "Duplicate source files")
    require(len({r["canonical"] for r in records}) == 22, "Duplicate canonical URLs")
    require(Counter(r["lang"] for r in records) == {"pt-BR": 8, "es": 7, "en": 7},
            "Unexpected language counts")
    indexed = {r["canonical"]: r for r in records}
    for record in records:
        for url in [record["canonical"], *record["alternates"].values()]:
            parsed = urlsplit(url)
            require(parsed.scheme == "https" and parsed.netloc == "lpvturismo.com"
                    and not parsed.query and not parsed.fragment, f"Invalid SEO URL: {url}")
            require(url in indexed, f"Unknown SEO URL: {url}")
        require(record["alternates"][record["lang"]] == record["canonical"],
                f"Missing self-reference: {record['id']}")
        require(record["alternates"]["x-default"] == record["alternates"]["pt-BR"],
                "x-default must be PT")
        for url in record["alternates"].values():
            require(indexed[url]["alternates"] == record["alternates"], "Non-reciprocal group")
        source = (ROOT / record["source"]).resolve()
        require(source.is_relative_to(ROOT / "pages"), "Source outside pages")
        require(source.is_file(), f"Missing source: {source}")


def validate_html(record):
    source = (ROOT / record["source"]).read_text(encoding="utf-8")
    parser = BalancedHTML()
    parser.feed(source)
    parser.close()
    require(not parser.errors and not parser.stack,
            f"Unbalanced HTML {record['source']}: {parser.errors} {parser.stack}")
    soup = BeautifulSoup(source, "html.parser")
    require(len(soup.select("h1")) == 1, f"Expected one H1: {record['id']}")
    require(not soup.select("html, head, body, main, title, meta, link[rel=canonical]"),
            f"Unexpected document/head elements in fragment: {record['id']}")
    require(len(soup.select("header.topbar")) == 1, "Expected one LPV header")
    require(len(soup.select("footer.lpv-site-footer")) == 1, "Expected one LPV footer")
    links = soup.select("footer.lpv-site-footer a.lpv-footer-privacy")
    require(len(links) == 1 and links[0].get("href") == "/politica-de-privacidade/"
            and links[0].get("hreflang") == "pt-BR", f"Invalid privacy link: {record['id']}")
    ids = [node["id"] for node in soup.select("[id]")]
    require(len(ids) == len(set(ids)), f"Duplicate HTML IDs: {record['id']}")
    for form in soup.select("form"):
        require(form.get("action") == "https://formsubmit.co/info@lpvturismo.com",
                "Unexpected form endpoint")
    return {"id": record["id"], "source": record["source"],
            "tag_balance": "pass", "privacy_link": "pass", "unique_ids": "pass",
            "single_h1_header_footer": "pass"}


def hreflang_html(record):
    return "\n".join(
        f'<link rel="alternate" hreflang="{lang}" href="{escape(url, quote=True)}">'
        for lang, url in record["alternates"].items()) + "\n"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build():
    page_map, records = load_records()
    checks = [validate_html(record) for record in records]
    css = ROOT / "css/lpv-style.css"
    require(css.read_bytes() == (ROOT / "docs/lpv-css-para-wordpress.css").read_bytes(),
            "WordPress CSS copy differs")
    # Write only known package files. Never delete unrelated workspace content.
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for record in records:
        target = PACKAGE / "html" / Path(record["source"]).relative_to("pages")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / record["source"], target)
        tags = PACKAGE / "hreflang" / f"{record['id']}.html"
        tags.parent.mkdir(parents=True, exist_ok=True)
        tags.write_text(hreflang_html(record), encoding="utf-8")
    language_map = {
        "approval_date": page_map["publication_state"]["approval_date"],
        "application": "Prepared only; apply on WordPress after review. Never advertise drafts.",
        "pages": [{key: record[key] for key in (
            "id", "source", "url", "family", "lang", "canonical", "alternates",
            "missing_direct_equivalents", "navigation_fallbacks_not_hreflang")}
            for record in records],
        "shared_legal_page": page_map["privacy"],
    }
    metadata = [{key: record[key] for key in ("id", "url", "lang", "title", "description", "canonical")}
                for record in records]
    write_json(ROOT / "docs/stage-4-language-map.json", language_map)
    write_json(ROOT / "docs/stage-4-aioseo-metadata.json", metadata)
    write_json(PACKAGE / "language-map.json", language_map)
    write_json(PACKAGE / "aioseo-metadata.json", metadata)
    write_json(PACKAGE / "url-map.json", page_map)
    with (PACKAGE / "aioseo-metadata.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata[0]))
        writer.writeheader()
        writer.writerows(metadata)
    lines = ["# Inventário das 22 páginas", "", "Gerado de `docs/page-map.json`; não editar esta cópia.",
             "", "| ID | Idioma | URL / canonical | Família | Equivalentes ausentes | Fonte |",
             "| --- | --- | --- | --- | --- | --- |"]
    for record in records:
        absent = ", ".join(record["missing_direct_equivalents"]) or "Nenhum"
        lines.append(f"| {record['id']} | {record['lang']} | {record['canonical']} | "
                     f"{record['family']} | {absent} | `{record['source']}` |")
    inventory = "\n".join(lines) + "\n"
    (ROOT / "docs/stage-4-page-inventory.md").write_text(inventory, encoding="utf-8")
    (PACKAGE / "PAGE-INVENTORY.md").write_text(inventory, encoding="utf-8")
    for source, name in [
        (css, "css/lpv-style.css"),
        (ROOT / "docs/stage-4-wordpress-checklist.md", "CHECKLIST.md"),
        (ROOT / "docs/stage-4-validation-report.md", "REVIEW-REPORT.md"),
        (ROOT / "docs/stage-4-public-observation.json", "PUBLIC-OBSERVATION.json"),
        (ROOT / "wordpress/templates/lpv-content-only.html", "wordpress/lpv-content-only.html"),
    ]:
        target = PACKAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    write_json(PACKAGE / "VALIDATION.json", {
        "scope": "Local structural validation, not W3C certification or WordPress runtime tests",
        "pages": checks, "metadata_rows": len(metadata), "reciprocal_hreflang": "pass",
        "css_copies_identical": True, "forms_submitted": 0, "wordpress_writes": 0,
    })
    expected_files = {
        "css/lpv-style.css", "language-map.json", "aioseo-metadata.json", "url-map.json",
        "aioseo-metadata.csv", "PAGE-INVENTORY.md", "CHECKLIST.md", "REVIEW-REPORT.md",
        "PUBLIC-OBSERVATION.json", "wordpress/lpv-content-only.html", "VALIDATION.json",
    }
    for record in records:
        expected_files.add("html/" + Path(record["source"]).relative_to("pages").as_posix())
        expected_files.add(f"hreflang/{record['id']}.html")
    manifest = {name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest()
                for name in sorted(expected_files)}
    write_json(PACKAGE / "manifest.json", manifest)
    archive = ROOT / "publication/lpv-wordpress-stage-4.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name in [*manifest, "manifest.json"]:
            zipped.write(PACKAGE / name, name)
    print(f"Prepared {len(records)} pages, 22 metadata rows and {len(manifest)} package files.")
    print(f"Review archive: {archive}")


if __name__ == "__main__":
    build()
