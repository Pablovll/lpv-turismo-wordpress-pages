import copy
import hashlib
import json
import unittest
import zipfile
from collections import Counter

from bs4 import BeautifulSoup
from scripts.build_wordpress_package import (
    ROOT, PACKAGE, BalancedHTML, hreflang_html, load_records, read_metadata,
    validate_html, validate_records,
)


class Stage4PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page_map, cls.records = load_records()

    def test_inventory_and_approval(self):
        self.assertEqual(len(self.records), 22)
        self.assertEqual(Counter(r["family"] for r in self.records)["lp_experiences"], 1)
        self.assertTrue(self.page_map["publication_state"]["en_owner_approved"])
        self.assertEqual(self.page_map["publication_state"]["en_intended_status"], "publish")
        self.assertEqual({r["status"] for r in self.records if r["lang"] == "en"}, {"publish"})

    def test_all_fragments_structurally_valid(self):
        for record in self.records:
            with self.subTest(page=record["id"]):
                validate_html(record)

    def test_balance_validator_rejects_broken_tags(self):
        parser = BalancedHTML()
        parser.feed("<section><div></section>")
        self.assertTrue(parser.errors)

    def test_triplets_and_pt_only_vertical(self):
        for record in self.records:
            tags = BeautifulSoup(hreflang_html(record), "html.parser").select("link")
            actual = {link["hreflang"]: link["href"] for link in tags}
            self.assertEqual(actual, record["alternates"])
            if record["family"] == "lp_experiences":
                self.assertEqual(set(actual), {"pt-BR", "x-default"})
                self.assertEqual(record["missing_direct_equivalents"], ["es", "en"])
            else:
                self.assertEqual(set(actual), {"pt-BR", "es", "en", "x-default"})

    def test_invalid_seo_urls_are_rejected(self):
        for suffix in ("?experience=mipim", "#lp-experiences"):
            records = copy.deepcopy(self.records)
            records[0]["canonical"] += suffix
            with self.assertRaises(ValueError):
                validate_records(records)

    def test_nonreciprocal_alternates_are_rejected(self):
        records = copy.deepcopy(self.records)
        del records[0]["alternates"]["es"]
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_metadata_unchanged_from_stage3_table(self):
        metadata = json.loads((PACKAGE / "aioseo-metadata.json").read_text(encoding="utf-8"))
        expected = read_metadata()
        self.assertEqual(len(metadata), 22)
        for row in metadata:
            self.assertEqual(row["title"], expected[row["url"]]["title"])
            self.assertEqual(row["description"], expected[row["url"]]["description"])
            self.assertEqual(row["canonical"], "https://lpvturismo.com" + row["url"])

    def test_html_copies_and_css_are_byte_identical(self):
        for record in self.records:
            source = ROOT / record["source"]
            packaged = PACKAGE / "html" / source.relative_to(ROOT / "pages")
            self.assertEqual(source.read_bytes(), packaged.read_bytes())
        css = (ROOT / "css/lpv-style.css").read_bytes()
        self.assertEqual(css, (PACKAGE / "css/lpv-style.css").read_bytes())
        self.assertEqual(css, (ROOT / "docs/lpv-css-para-wordpress.css").read_bytes())

    def test_generated_language_map_and_tags(self):
        language_map = json.loads((PACKAGE / "language-map.json").read_text(encoding="utf-8"))
        self.assertEqual(len(language_map["pages"]), 22)
        for record, row in zip(self.records, language_map["pages"]):
            self.assertEqual(record["alternates"], row["alternates"])
            self.assertEqual(record["lang"], row["lang"])
            self.assertEqual((PACKAGE / "hreflang" / f"{record['id']}.html").read_text(encoding="utf-8"),
                             hreflang_html(record))

    def test_archive_manifest(self):
        manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        with zipfile.ZipFile(ROOT / "publication/lpv-wordpress-stage-4.zip") as archive:
            self.assertEqual(set(archive.namelist()), {*manifest, "manifest.json"})
            for name, expected in manifest.items():
                data = (PACKAGE / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected)
                self.assertEqual(archive.read(name), data)

    def test_content_only_template(self):
        source = (ROOT / "wordpress/templates/lpv-content-only.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("<!-- wp:post-content "), 1)
        self.assertNotIn("wp:post-title", source)
        self.assertNotIn("wp:template-part", source)
        self.assertEqual(len(BeautifulSoup(source, "html.parser").select("main")), 1)


if __name__ == "__main__":
    unittest.main()
