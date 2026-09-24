import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
import zipfile

from bs4 import BeautifulSoup
from scripts.build_wordpress_package import ROOT, BalancedHTML, load_records

PLUGIN = ROOT / "wordpress/plugins/lpv-page-templates"
PACKAGE = ROOT / "publication/stage-6"
PHP = os.environ.get("PHP_BINARY") or shutil.which("php")
CORE = os.environ.get("WP_TEMPLATE_CORE_DIR")


class Stage6StaticTests(unittest.TestCase):
    def test_ids_and_paths_match_approved_map(self):
        source = (PLUGIN / "lpv-page-templates.php").read_text(encoding="utf-8")
        rows = re.findall(r"^\s*(\d+)\s*=> '([^']+)'", source, re.MULTILINE)
        self.assertEqual(len(rows), 22)
        self.assertEqual({int(key): value for key, value in rows},
                         {r["id"]: r["url"] for r in load_records()[1]})

    def test_scoped_native_hooks_only(self):
        source = (PLUGIN / "lpv-page-templates.php").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"add_(?:action|filter)\( '([^']+)'", source),
                         ["page_template_hierarchy", "frontpage_template_hierarchy", "init", "wp"])
        self.assertIn("remove_filter( 'the_content', 'wpautop' )", source)
        self.assertIn("lpv_page_templates_is_managed_request()", source)
        self.assertIn("register_block_template(", source)
        self.assertIn("Requires at least: 6.7", source)
        self.assertIn("if ( ! defined( 'ABSPATH' ) )", source)
        self.assertNotRegex(source, r"\b(?:wp_remote_\w+|curl_\w+|update_\w+|delete_\w+|"
                            r"wp_insert_\w+|wp_update_\w+|remove_all_\w+|eval|exec)\s*\(")
        self.assertNotRegex(source, r"\$_(?:GET|POST|REQUEST|SERVER)|\$wpdb|<meta|<script|<title|"
                            r"rel=.canonical|wp_head\(|wp_footer\(|echo\s|print\s")
        self.assertIn("__DIR__ . '/templates/lpv-content-only.html'", source)

    def test_template_identity_and_22_expected_structures(self):
        template = (ROOT / "wordpress/templates/lpv-content-only.html").read_bytes()
        self.assertEqual(template, (PLUGIN / "templates/lpv-content-only.html").read_bytes())
        text = template.decode("utf-8")
        self.assertNotRegex(text, r"wp:(?:template-part|post-title|post-featured-image)|display\s*:\s*none")
        slot = '<!-- wp:post-content {"align":"full","layout":{"type":"default"}} /-->'
        self.assertEqual(text.count(slot), 1)
        for record in load_records()[1]:
            with self.subTest(page=record["id"]):
                # Structural composition, not WordPress block rendering.
                content = (ROOT / record["source"]).read_text(encoding="utf-8")
                rendered = text.replace(slot, '<div class="wp-block-post-content">' + content + '</div>')
                parser = BalancedHTML()
                parser.feed(rendered)
                parser.close()
                self.assertEqual(parser.errors, [])
                self.assertEqual(parser.stack, [])
                soup = BeautifulSoup(rendered, "html.parser")
                for selector in ("main", "h1", "header.topbar", "footer.lpv-site-footer"):
                    self.assertEqual(len(soup.select(selector)), 1, selector)
                self.assertFalse(soup.select(".wp-block-post-title, .wp-block-template-part"))

    def test_package_manifest_and_zip(self):
        manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
        with zipfile.ZipFile(ROOT / "publication/lpv-wordpress-stage-6.zip") as archive:
            self.assertEqual(set(archive.namelist()), {*manifest, "manifest.json"})
            self.assertEqual(archive.testzip(), None)
            for name, digest in manifest.items():
                data = (PACKAGE / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                self.assertEqual(archive.read(name), data)
        self.assertFalse(any(name.startswith("hreflang/") for name in manifest))
        self.assertEqual(sum(name.startswith("html/") for name in manifest), 22)
        self.assertEqual((PACKAGE / "RUNBOOK.md").read_bytes(),
                         (ROOT / "docs/stage-6-wordpress-integration.md").read_bytes())

    def test_approved_assets_and_plugin_unchanged_in_bundle(self):
        for record in load_records()[1]:
            relative = record["source"].removeprefix("pages/")
            self.assertEqual((PACKAGE / "html" / relative).read_bytes(),
                             (ROOT / record["source"]).read_bytes())
        self.assertEqual((PACKAGE / "css/lpv-style.css").read_bytes(),
                         (ROOT / "css/lpv-style.css").read_bytes())
        for name in ("language-map.json", "url-map.json", "aioseo-metadata.json"):
            self.assertEqual((PACKAGE / name).read_bytes(),
                             (ROOT / "publication/stage-4" / name).read_bytes())
        self.assertEqual((PACKAGE / "aioseo-metadata.csv").read_bytes(),
                         (ROOT / "publication/stage-4/aioseo-metadata.csv").read_bytes())
        self.assertEqual((PACKAGE / "plugins/lpv-language-seo-1.0.0.zip").read_bytes(),
                         (ROOT / "publication/stage-5/lpv-language-seo-1.0.0.zip").read_bytes())
        with zipfile.ZipFile(PACKAGE / "plugins/lpv-page-templates-1.0.1.zip") as archive:
            self.assertEqual(set(archive.namelist()), {"lpv-page-templates/" + n for n in (
                "lpv-page-templates.php", "README.md", "templates/lpv-content-only.html")})
            for name in archive.namelist():
                self.assertEqual(archive.read(name), (ROOT / "wordpress/plugins" / name).read_bytes())

    def test_manual_application_order_and_exclusions(self):
        plan = json.loads((PACKAGE / "application-plan.json").read_bytes())
        self.assertFalse(plan["automatic_deployment"])
        self.assertEqual(plan["order"], ["backup", "template", "language_plugin", "css", "html",
                                        "aioseo", "en_publication_status", "cache_purge", "public_html_audit"])
        self.assertEqual(plan["front_page"], {"show_on_front": "page", "page_on_front": 7})
        self.assertEqual(len(plan["pages"]), 22)
        self.assertEqual(plan["excluded"], ["privacy", "posts", "archives", "search", "404"])

    def test_staging_build_is_reproducible(self):
        archive = ROOT / "publication/lpv-wordpress-stage-6.zip"
        before = archive.read_bytes()
        result = subprocess.run([sys.executable, "scripts/build_staging_package.py"], cwd=ROOT,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, archive.read_bytes())


@unittest.skipUnless(PHP, "Set PHP_BINARY for PHP checks")
class Stage6PHPTests(unittest.TestCase):
    def run_php(self, *args):
        result = subprocess.run([PHP, *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def test_php_lint_and_direct_access_guard(self):
        for path in (PLUGIN / "lpv-page-templates.php", ROOT / "tests/php/test_lpv_page_templates.php"):
            self.assertIn("No syntax errors", self.run_php("-l", path))
        self.assertEqual(self.run_php(PLUGIN / "lpv-page-templates.php"), "")

    @unittest.skipUnless(CORE, "Set WP_TEMPLATE_CORE_DIR to local WordPress 6.7+ core")
    def test_native_registry_parser_and_resolution(self):
        output = self.run_php(ROOT / "tests/php/test_lpv_page_templates.php", "--wordpress-core=" + CORE)
        self.assertRegex(output, r"PASS: \d+ assertions; template scope and native resolution")


if __name__ == "__main__":
    unittest.main()
