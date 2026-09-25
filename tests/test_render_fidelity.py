import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.audit_production import ProductionReader, normalized_probe_result
from scripts.content_fidelity import (compare_rendered_content, compare_rendered_images,
                                      compare_script_sources, compare_stored_content,
                                      optimized_script_delivery)


FIXTURES = Path(__file__).parent / "fixtures/render-fidelity"


class RenderFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approved = (FIXTURES / "approved.html").read_text(encoding="utf-8")
        cls.cosmetic = (FIXTURES / "cosmetic.html").read_text(encoding="utf-8")
        cls.derived = (FIXTURES / "derived-srcset.html").read_text(encoding="utf-8")
        cls.negative = json.loads((FIXTURES / "negative-cases.json").read_text(encoding="utf-8"))

    def test_identical_and_cosmetic_html_preserve_semantics(self):
        self.assertTrue(compare_rendered_content(self.approved, self.approved)["preserved"])
        cosmetic = compare_rendered_content(self.approved, self.cosmetic)
        self.assertTrue(cosmetic["preserved"], cosmetic["failures"])
        self.assertTrue(compare_rendered_images(self.approved, self.cosmetic)["primary_preserved"])

    def test_html_comments_are_not_visible_text(self):
        without_comment = self.approved.replace(
            "<!-- Approved editorial note removed by HTML optimization. -->\n", "")
        result = compare_rendered_content(self.approved, without_comment)
        self.assertTrue(result["preserved"], result)

    def test_equal_counts_can_still_have_text_and_script_failures(self):
        changed = self.approved.replace("ritmo do grupo", "ritmo sem grupo", 1)
        changed = changed.replace("button.dataset.clicked = 'yes'",
                                  "button.dataset.clicked = 'no'", 1)
        result = compare_rendered_content(self.approved, changed)
        self.assertEqual(result["expected"], result["observed"])
        self.assertIn("text", result["failures"])
        self.assertIn("scripts", result["failures"])
        self.assertNotEqual(result["diagnostics"]["text"]["expected_sha256"],
                            result["diagnostics"]["text"]["observed_sha256"])
        self.assertIn("code", result["diagnostics"]["scripts"][0]["differences"])

    def test_text_diagnostics_only_expose_approved_or_redacted_tokens(self):
        changed = self.approved.replace("ritmo do grupo", "cliente@example.test 5491112345678", 1)
        diagnostic = compare_rendered_content(self.approved, changed)["diagnostics"]["text"]
        serialized = json.dumps(diagnostic, ensure_ascii=False)
        self.assertNotIn("cliente@example.test", serialized)
        self.assertNotIn("5491112345678", serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_entity_typography_attribute_order_and_safe_image_attributes_pass(self):
        rendered = self.cosmetic.replace("ritmo do grupo", "ritmo do grupo")
        rendered = rendered.replace("Uma experiência", "Uma experi&#234;ncia")
        self.assertTrue(compare_rendered_content(self.approved, rendered)["preserved"])

    def test_valid_litespeed_placeholder_and_wordpress_srcset_are_separate(self):
        result = compare_rendered_images(self.approved, self.derived)
        self.assertTrue(result["primary_preserved"], result["failures"])
        self.assertTrue(result["derived_valid"], result["failures"])
        self.assertEqual(len(result["derived_http_urls"]), 2)

    def test_css_stylesheet_and_font_urls_are_not_image_probes(self):
        result = compare_rendered_images(self.approved, self.cosmetic)
        urls = [target["url"] for target in result["probe_targets"]]
        self.assertNotIn("https://fonts.googleapis.com/css2?family=Inter", urls)
        self.assertIn("https://lpvturismo.com/wp-content/uploads/2026/06/hero.jpg", urls)

    def test_external_or_unrelated_derived_url_fails(self):
        unrelated = self.derived.replace(
            "https://lpvturismo.com/wp-content/uploads/2026/06/photo-300x200.jpg",
            "https://external.example/photo-300x200.jpg",
        )
        result = compare_rendered_images(self.approved, unrelated)
        self.assertFalse(result["derived_valid"])
        self.assertIn("invalid_derived_url:0:data-srcset", result["failures"])

    def test_image_probe_statuses_and_timeout_remain_blocking(self):
        images = compare_rendered_images(self.approved, self.derived)
        derived_target = next(target for target in images["probe_targets"]
                              if "srcset" in target["source"])
        for value in (
                {"http_status": 404, "reachable": False},
                {"http_status": 500, "reachable": False},
                {"http_status": None, "error": "timeout", "reachable": False}):
            with self.subTest(value=value):
                result = {**derived_target,
                          **normalized_probe_result(derived_target["url"], value)}
                self.assertIn("srcset", result["source"])
                self.assertFalse(result["reachable"])

    def test_image_probe_records_404_500_and_timeout_details(self):
        url = "https://lpvturismo.com/wp-content/uploads/2026/06/image.jpg?private=redacted"
        for status in (404, 500):
            with self.subTest(status=status):
                error = HTTPError(url, status, "fixture", {"Content-Type": "text/html"}, io.BytesIO())
                reader = ProductionReader()
                with patch.object(reader.opener, "open", side_effect=error):
                    result = reader.probe_image(url)
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["content_type"], "text/html")
                self.assertEqual(result["error"], "http_error")
                self.assertNotIn("private=", result["url"])
                self.assertFalse(result["reachable"])
        reader = ProductionReader()
        with patch.object(reader.opener, "open", side_effect=TimeoutError()):
            result = reader.probe_image(url)
        self.assertEqual(result["error"], "timeout")
        self.assertFalse(result["reachable"])

    def test_unexpected_image_host_is_rejected_without_network(self):
        result = ProductionReader().probe_image("https://external.example/image.jpg")
        self.assertFalse(result["reachable"])
        self.assertEqual(result["error"], "policy_rejected")

    def test_stored_contract_is_exact_and_keeps_editorial_urls(self):
        exact = compare_stored_content(self.approved, self.approved)
        self.assertTrue(exact["content_preserved"])
        self.assertTrue(exact["image_urls_preserved"])
        whitespace = compare_stored_content(self.approved, self.approved + "\n")
        self.assertFalse(whitespace["content_preserved"])
        replaced = compare_stored_content(self.approved, self.approved.replace(
            "photo-scaled.jpg", "another-photo.jpg"))
        self.assertFalse(replaced["image_urls_preserved"])

    def test_stored_script_source_only_normalizes_encoding_and_newlines(self):
        crlf = self.approved.replace("\n", "\r\n")
        self.assertTrue(compare_script_sources(self.approved, crlf)["preserved"])
        comments_removed = self.approved.replace("// analytics fixture\n", "", 1)
        if comments_removed == self.approved:
            comments_removed = self.approved.replace("const endpoint", "/* changed */const endpoint", 1)
        self.assertFalse(compare_script_sources(self.approved, comments_removed)["preserved"])
        endpoint = self.approved.replace("/wp-json/lpv/v1/context", "/wp-json/lpv/v2/context", 1)
        self.assertFalse(compare_script_sources(self.approved, endpoint)["preserved"])
        handler = self.approved.replace("button.addEventListener", "button.removeEventListener", 1)
        self.assertFalse(compare_script_sources(self.approved, handler)["preserved"])

    def test_optimized_delivery_is_diagnostic_not_lexical_equivalence(self):
        transformed = self.cosmetic.replace("='yes');</script>", "='yes')</script>", 1)
        strict = compare_rendered_content(self.approved, transformed)
        optimized = compare_rendered_content(self.approved, transformed, strict_scripts=False)
        self.assertIn("scripts", strict["failures"])
        self.assertNotIn("scripts", optimized["failures"])
        delivery = optimized_script_delivery(self.approved, transformed)
        self.assertTrue(delivery["detected"])
        self.assertEqual(delivery["records"][0]["delivery"], "litespeed")

    def test_required_negative_cases_fail_without_weakening_the_auditor(self):
        content_cases = {
            "text_removed", "word_removed", "phrase_altered", "cta_altered",
            "cta_removed", "href_changed", "form_action_changed", "field_name_changed",
            "script_removed", "script_code_altered", "script_endpoint_altered",
            "script_handler_removed", "class_removed", "id_removed", "id_duplicated",
        }
        image_cases = {"image_url_changed", "image_removed"}
        for name, replacement in self.negative.items():
            with self.subTest(case=name):
                rendered = self.approved.replace(*replacement, 1)
                if name in content_cases:
                    result = compare_rendered_content(self.approved, rendered)
                    self.assertFalse(result["preserved"], name)
                if name in image_cases:
                    result = compare_rendered_images(self.approved, rendered)
                    self.assertFalse(result["primary_preserved"], name)


if __name__ == "__main__":
    unittest.main()
