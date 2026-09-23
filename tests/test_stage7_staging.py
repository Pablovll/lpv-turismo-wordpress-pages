import copy
import html
import io
import json
import shutil
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bs4 import BeautifulSoup
from scripts.audit_staging import PACKAGE, StagingReader, audit, inspect_page, staging_origin
from scripts.preflight_staging import package_preflight, sensitive_indicators

ROWS = json.loads((PACKAGE / "language-map.json").read_bytes())["pages"]
META = {r["id"]: r for r in json.loads((PACKAGE / "aioseo-metadata.json").read_bytes())}
ORIGIN = "https://staging.example.test"


def document(row, published=False):
    head = '<title>' + html.escape(META[row["id"]]["title"]) + '</title>'
    head += '<meta name="description" content="' + html.escape(META[row["id"]]["description"], quote=True) + '">'
    head += '<link rel="canonical" href="' + ORIGIN + row["url"] + '">'
    if published:
        head += ''.join(f'<link rel="alternate" hreflang="{lang}" href="{url}">' for lang, url in row["alternates"].items())
    content = (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_text(encoding="utf-8")
    css = (PACKAGE / "css/lpv-style.css").read_text(encoding="utf-8")
    return f'<html lang="{row["lang"]}"><head>{head}<style>{css}</style></head><body><main><div class="wp-block-post-content">{content}</div></main></body></html>'


def response(row, body=None):
    return {"status": 200, "url": ORIGIN + row["url"], "body": document(row) if body is None else body, "headers": {}}


class StagingPreflightTests(unittest.TestCase):
    def test_real_stage6_package(self):
        result = package_preflight()
        self.assertEqual(result["status"], "APROVADO")
        self.assertEqual(result["html_files"], 22)
        self.assertEqual(result["manifest_files"], 36)

    def test_changed_file_blocks_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "stage-6"
            shutil.copytree(PACKAGE, folder)
            (folder / "css/lpv-style.css").write_text("changed", encoding="utf-8")
            result = package_preflight(folder, PACKAGE.parent / "lpv-wordpress-stage-6.zip")
            self.assertEqual(result["status"], "BLOQUEADOR")
            self.assertIn("css/lpv-style.css", result["failures"])

    def test_redacted_secret_and_email_detection(self):
        token = "gh" + "p_" + "x" * 36
        findings = sensitive_indicators("config.txt", token.encode())
        self.assertEqual(findings[0]["rule"], "access_token")
        self.assertNotIn(token, json.dumps(findings))
        address = "person" + "@" + "notexample.com"
        self.assertEqual(sensitive_indicators("data.txt", address.encode())[0]["rule"], "email_requires_review")
        self.assertFalse(sensitive_indicators("form.html", b'info@lpvturismo.com seuemail@exemplo.com tuemail@ejemplo.com'))

    def test_nested_zip_and_backup_detection(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("backup.sql", "database export")
        result = sensitive_indicators("bundle.zip", stream.getvalue())
        self.assertEqual(result, [{"file": "bundle.zip!/backup.sql", "rule": "sensitive_filename"}])


class StagingAuditTests(unittest.TestCase):
    def test_production_credentials_and_ambiguous_origins_rejected(self):
        for url in ("https://lpvturismo.com/", "https://WWW.LPVTurismo.com:443/", "https://lpvturismo.com./",
                    "https://user:pass@staging.example.test/", "http://staging.example.test",
                    "https://staging.example.test/subdir", "https://staging.example.test/?token=hidden",
                    "https://staging.example.test/#fragment", "file:///tmp/page.html"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                staging_origin(url)
        self.assertEqual(staging_origin(ORIGIN + "/"), ORIGIN)

    def test_get_rejects_escape_and_traversal(self):
        reader = StagingReader("http://127.0.0.1:9")
        for path in ("//lpvturismo.com/", "https://lpvturismo.com/", "/?action=write", "/a/../b", "/%2fadmin", "/a\\b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                reader.get(path)
        with self.assertRaises(ValueError):
            StagingReader("http://127.0.0.1:9", "user", "pass")
        with self.assertRaises(ValueError):
            StagingReader(ORIGIN, "user", None)

    def test_all_22_expected_documents_without_hreflang(self):
        for row in ROWS:
            with self.subTest(page=row["id"]):
                result = inspect_page(row, META[row["id"]], response(row), ORIGIN, "staging", "suppressed")
                self.assertNotIn("BLOQUEADOR", result["checks"].values())
                self.assertEqual(result["checks"]["published_reciprocity"], "NAO TESTADO")
                self.assertEqual(result["checks"]["horizontal_overflow"], "NAO TESTADO")

    def test_published_sets_reciprocal_self_and_lp_pt_only(self):
        for row in ROWS:
            with self.subTest(page=row["id"]):
                result = inspect_page(row, META[row["id"]], response(row, document(row, True)), ORIGIN, "staging", "published")
                self.assertNotIn("BLOQUEADOR", result["checks"].values())
        lp = next(r for r in ROWS if r["id"] == 255)
        self.assertEqual(set(lp["alternates"]), {"pt-BR", "x-default"})
        body = document(lp, True).replace('</head>', '<link rel="alternate" hreflang="en" href="https://lpvturismo.com/en/services/"></head>')
        result = inspect_page(lp, META[255], response(lp, body), ORIGIN, "staging", "published")
        self.assertEqual(result["checks"]["hreflang_exact_group_self_xdefault"], "BLOQUEADOR")

    def test_missing_or_duplicate_hreflang_blocks_published_mode(self):
        row = ROWS[0]
        for body in (document(row), document(row, True).replace('</head>', '<link rel="alternate" hreflang="en" href="https://lpvturismo.com/en/"></head>')):
            result = inspect_page(row, META[row["id"]], response(row, body), ORIGIN, "staging", "published")
            self.assertEqual(result["checks"]["hreflang_exact_group_self_xdefault"], "BLOQUEADOR")

    def test_dom_lang_metadata_and_css_regressions(self):
        row = ROWS[0]
        mutations = {
            "main": lambda s: s.main.append(s.new_tag("main")),
            "h1": lambda s: s.main.append(s.new_tag("h1")),
            "lang": lambda s: s.html.attrs.update(lang="en"),
            "canonical_unique_expected": lambda s: s.head.append(copy.copy(s.select_one('link[rel="canonical"]'))),
            "title": lambda s: setattr(s.title, "string", "Wrong title"),
            "description": lambda s: s.select_one('meta[name="description"]').attrs.update(content="Wrong"),
            "absent:.wp-block-post-title": lambda s: s.main.append(s.new_tag("h1", attrs={"class": "wp-block-post-title"})),
            "absent:.wp-block-template-part": lambda s: s.main.append(s.new_tag("header", attrs={"class": "wp-block-template-part"})),
            "absent:.wp-block-post-featured-image": lambda s: s.main.append(s.new_tag("figure", attrs={"class": "wp-block-post-featured-image"})),
        }
        for key, mutate in mutations.items():
            soup = BeautifulSoup(document(row), "html.parser")
            mutate(soup)
            result = inspect_page(row, META[row["id"]], response(row, str(soup)), ORIGIN, "staging", "suppressed")
            self.assertEqual(result["checks"][key], "BLOQUEADOR", key)

    def test_sanitized_forms_scripts_aria_classes_ids_and_links(self):
        row = next(r for r in ROWS if r["id"] == 19)
        for selector, attribute in (("script", None), ("form", None), ("[aria-label]", "aria-label"),
                                    ("[class]", "class"), ("[id]", "id"), ("a[href]", "href")):
            soup = BeautifulSoup(document(row), "html.parser")
            element = soup.select_one(".wp-block-post-content").select_one(selector)
            if attribute:
                del element[attribute]
            else:
                element.decompose()
            result = inspect_page(row, META[19], response(row, str(soup)), ORIGIN, "staging", "suppressed")
            self.assertEqual(result["checks"]["approved_fragment_features_scripts_text"], "BLOQUEADOR")

    def test_missing_css_and_private_response_are_not_approved_or_logged(self):
        row = next(r for r in ROWS if r["id"] == 19)
        soup = BeautifulSoup(document(row), "html.parser")
        for style in soup.select("style"):
            style.decompose()
        private_value = "synthetic-private-value"
        soup.select_one("input")["value"] = private_value
        raw = response(row, str(soup))
        raw["headers"] = {"Set-Cookie": "private-session-placeholder"}
        result = inspect_page(row, META[19], raw, ORIGIN, "staging", "suppressed")
        self.assertEqual(result["checks"]["approved_inline_css"], "NAO TESTADO")
        self.assertEqual(result["checks"]["approved_fragment_features_scripts_text"], "BLOQUEADOR")
        self.assertNotIn(private_value, json.dumps(result))
        self.assertNotIn("private-session-placeholder", json.dumps(result))

    def test_unreviewed_http_seo_headers_block(self):
        row = ROWS[0]
        raw = response(row)
        raw["headers"] = {"Link": '<https://lpvturismo.com/>; rel="canonical"'}
        result = inspect_page(row, META[row["id"]], raw, ORIGIN, "staging", "suppressed")
        self.assertEqual(result["checks"]["no_unreviewed_http_link_seo"], "BLOQUEADOR")

    def test_full_fake_audit_never_approves_staging(self):
        class FakeReader:
            origin = ORIGIN
            calls = []

            def get(self, path):
                self.calls.append(path)
                if path == "/politica-de-privacidade/":
                    return {"status": 200, "url": ORIGIN + path, "body": "<html><main>Policy fixture</main></html>"}
                row = next(r for r in ROWS if r["url"] == path)
                return response(row)

        reader = FakeReader()
        report = audit(reader)
        self.assertEqual(len(reader.calls), 23)
        self.assertEqual(report["status"], "PENDENTE")
        self.assertFalse(report["staging_approved"])
        self.assertEqual(report["forms_sent"], 0)

    def test_real_loopback_get_does_not_follow_redirect(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.command, self.path))
                self.send_response(302)
                self.send_header("Location", "https://lpvturismo.com/")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = StagingReader(f"http://127.0.0.1:{server.server_port}").get("/redirect")
            self.assertEqual(result["status"], 302)
            self.assertEqual(calls, [("GET", "/redirect")])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
