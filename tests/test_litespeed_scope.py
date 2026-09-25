import re
import unittest

from scripts.build_wordpress_package import ROOT, load_records


PLUGIN = ROOT / "wordpress/plugins/lpv-page-templates/lpv-page-templates.php"


class LiteSpeedScopeTests(unittest.TestCase):
    def test_exact_approved_routes_are_the_only_positive_scope(self):
        source = PLUGIN.read_text(encoding="utf-8")
        rows = {int(key): path for key, path in re.findall(
            r"^\s*(\d+)\s*=> '([^']+)'", source, re.MULTILINE)}
        self.assertEqual(rows, {row["id"]: row["url"] for row in load_records()[1]})
        self.assertEqual(len(rows), 22)
        self.assertIn("lpv_page_templates_request_path() !== $paths[ $id ]", source)
        self.assertNotRegex(source, r"(?:strpos|str_starts_with|preg_match)\s*\([^\n]*\$paths")

    def test_all_negative_contexts_are_explicit(self):
        source = PLUGIN.read_text(encoding="utf-8")
        for guard in ("is_admin()", "wp_doing_ajax()", "wp_doing_cron()", "REST_REQUEST",
                      "is_feed()", "is_embed()", "is_preview()", "is_search()", "is_404()",
                      "wp-login.php", "is_singular( 'page' )"):
            with self.subTest(guard=guard):
                self.assertIn(guard, source)
        self.assertIn("? false : $can_optimize", source)
        self.assertNotIn("update_option", source)
        self.assertNotIn("delete_option", source)

    def test_remote_harness_covers_routes_and_negative_contexts(self):
        harness = (ROOT / "tests/php/test_lpv_litespeed_scope.php").read_text(encoding="utf-8")
        for value in ("22", "wp-login.php", "REST_REQUEST", "politica-de-privacidade",
                      "Nonmapped page excluded", "Posts and archives excluded", "passeios%2F"):
            self.assertIn(value, harness)


if __name__ == "__main__":
    unittest.main()
