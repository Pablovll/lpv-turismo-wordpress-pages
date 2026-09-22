import hashlib
import json
import os
import re
import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "wordpress/plugins/lpv-language-seo/lpv-language-seo.php"
PHP = os.environ.get("PHP_BINARY") or shutil.which("php")
WP_CORE = os.environ.get("WP_CORE_DIR")


class Stage5StaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PLUGIN.read_text(encoding="utf-8")
        cls.approved = json.loads((ROOT / "docs/stage-4-language-map.json").read_text(encoding="utf-8"))

    def test_literal_map_matches_all_three_sources(self):
        # Require the explicit literal map shape; the PHP harness also checks groups at runtime.
        rows = re.findall(r"'(pt-BR|es|en)' => array\( 'id' => (\d+), 'url' => '([^']+)' \)", self.source)
        self.assertEqual(len(rows), 22)
        actual = {int(page_id): (lang, url) for lang, page_id, url in rows}
        expected = {row["id"]: (row["lang"], row["canonical"]) for row in self.approved["pages"]}
        self.assertEqual(actual, expected)
        page_map = json.loads((ROOT / "docs/page-map.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, {p["id"]: (p["lang"], page_map["site"] + p["url"])
                                  for pages in page_map["pages"].values() for p in pages.values()})
        packaged = json.loads((ROOT / "publication/stage-4/language-map.json").read_text(encoding="utf-8"))
        self.assertEqual(self.approved, packaged)

    def test_only_required_hooks(self):
        hooks = re.findall(r"add_(?:filter|action)\( '([^']+)'", self.source)
        self.assertEqual(hooks, ["language_attributes", "wp_head"])
        self.assertIn("new WP_HTML_Tag_Processor", self.source)
        self.assertIn("esc_attr( $language )", self.source)
        self.assertIn("esc_url( $url )", self.source)

    def test_no_competing_metadata_or_io(self):
        self.assertNotRegex(self.source, r"(?i)<(?:meta|title|script)|rel=[\"']canonical|application/ld\+json")
        self.assertNotRegex(self.source, r"\b(?:wp_remote_\w+|curl_\w+|file_get_contents|fopen|fsockopen|"
                            r"update_option|add_option|delete_option|wp_update_post|wp_insert_post|"
                            r"update_post_meta|register_activation_hook|register_deactivation_hook|"
                            r"exec|shell_exec|system|eval|remove_all_actions)\s*\(")
        self.assertNotRegex(self.source, r"\$_(?:GET|POST|REQUEST|COOKIE|SERVER)|\$wpdb")

    def test_lp_has_no_fake_translation(self):
        group = self.source.split("'lp_experiences' => array(", 1)[1].split("\n\t\t),", 1)[0]
        self.assertIn("'pt-BR'", group)
        self.assertNotIn("'es'", group)
        self.assertNotIn("'en'", group)
        self.assertNotIn("#lp-experiences", self.source)

    def test_installation_rollback_and_minimum_requirements(self):
        self.assertIn("Requires at least: 6.2", self.source)
        self.assertIn("Requires PHP: 7.4", self.source)
        self.assertIn("if ( ! defined( 'ABSPATH' ) )", self.source)
        readme = PLUGIN.with_name("README.md").read_text(encoding="utf-8")
        for topic in ("## Instalação", "## Rollback", "## Checklist", "## Conflitos", "## Testes locais"):
            self.assertIn(topic, readme)

    def test_installable_package_is_exact_and_isolated(self):
        folder = ROOT / "publication/stage-5"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        archive = folder / manifest["archive"]
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), manifest["archive_sha256"])
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(set(zipped.namelist()), {"lpv-language-seo/lpv-language-seo.php", "lpv-language-seo/README.md"})
            for name, digest in manifest["files"].items():
                source = PLUGIN.parent / Path(name).name
                self.assertEqual(zipped.read(name), source.read_bytes())
                self.assertEqual(hashlib.sha256(zipped.read(name)).hexdigest(), digest)


@unittest.skipUnless(PHP, "PHP not available; set PHP_BINARY for runtime checks")
class Stage5PHPTests(unittest.TestCase):
    def run_php(self, *args):
        result = subprocess.run([PHP, *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def test_php_lint(self):
        for path in (PLUGIN, ROOT / "tests/php/test_lpv_language_seo.php"):
            self.assertIn("No syntax errors", self.run_php("-l", path))

    def test_direct_access_guard(self):
        self.assertEqual(self.run_php(PLUGIN), "")

    @unittest.skipUnless(WP_CORE, "Set WP_CORE_DIR to a local WordPress 6.2+ core")
    def test_behavior_with_native_html_api_and_escaping(self):
        output = self.run_php(ROOT / "tests/php/test_lpv_language_seo.php", "--wordpress-core=" + WP_CORE)
        self.assertRegex(output, r"PASS: \d+ assertions; all 22 pages")


if __name__ == "__main__":
    unittest.main()
