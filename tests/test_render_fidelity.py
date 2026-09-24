import json
import unittest
from pathlib import Path

from scripts.content_fidelity import (compare_rendered_content, compare_rendered_images,
                                      compare_stored_content)


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

    def test_entity_typography_attribute_order_and_safe_image_attributes_pass(self):
        rendered = self.cosmetic.replace("ritmo do grupo", "ritmo do grupo")
        rendered = rendered.replace("Uma experiência", "Uma experi&#234;ncia")
        self.assertTrue(compare_rendered_content(self.approved, rendered)["preserved"])

    def test_valid_litespeed_placeholder_and_wordpress_srcset_are_separate(self):
        result = compare_rendered_images(self.approved, self.derived)
        self.assertTrue(result["primary_preserved"], result["failures"])
        self.assertTrue(result["derived_valid"], result["failures"])
        self.assertEqual(len(result["derived_http_urls"]), 2)

    def test_external_or_unrelated_derived_url_fails(self):
        unrelated = self.derived.replace(
            "https://lpvturismo.com/wp-content/uploads/2026/06/photo-300x200.jpg",
            "https://external.example/photo-300x200.jpg",
        )
        result = compare_rendered_images(self.approved, unrelated)
        self.assertFalse(result["derived_valid"])
        self.assertIn("invalid_derived_url:0:data-srcset", result["failures"])

    def test_stored_contract_is_exact_and_keeps_editorial_urls(self):
        exact = compare_stored_content(self.approved, self.approved)
        self.assertTrue(exact["content_preserved"])
        self.assertTrue(exact["image_urls_preserved"])
        whitespace = compare_stored_content(self.approved, self.approved + "\n")
        self.assertFalse(whitespace["content_preserved"])
        replaced = compare_stored_content(self.approved, self.approved.replace(
            "photo-scaled.jpg", "another-photo.jpg"))
        self.assertFalse(replaced["image_urls_preserved"])

    def test_required_negative_cases_fail_without_weakening_the_auditor(self):
        content_cases = {
            "text_removed", "cta_removed", "href_changed", "form_action_changed",
            "field_name_changed", "script_removed", "class_removed", "id_removed",
            "id_duplicated",
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
