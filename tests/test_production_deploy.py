import gzip
import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.audit_production import ORIGIN, audit
from scripts.backup_production import validate_backup
from scripts import deploy_production
from scripts.deploy_production import (AUTHORIZATION, apply_seo, exception_record, execute,
                                       failure_with_rollback, make_content_payload,
                                       parse_helper_result, state_identity_failures)
from scripts.production_common import PACKAGE, ROOT, load_metadata, load_pages, sha256_bytes

ROWS = load_pages()
META = load_metadata()


def production_document(row):
    content = (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_text(encoding="utf-8")
    head = f'<title>{html.escape(META[row["id"]]["title"])}</title>'
    head += '<meta name="description" content="' + html.escape(META[row["id"]]["description"], quote=True) + '">'
    head += f'<link rel="canonical" href="{row["canonical"]}">'
    head += ''.join(f'<link rel="alternate" hreflang="{language}" href="{url}">' for language, url in row["alternates"].items())
    return (f'<html lang="{row["lang"]}"><head>{head}<!-- aioseo --></head><body><main>'
            f'<div class="wp-block-post-content">{content}</div></main></body></html>')


class ProductionAuditTests(unittest.TestCase):
    def test_complete_fake_production_audit(self):
        class Reader:
            def get(self, path):
                if path == "/politica-de-privacidade/":
                    return {"status": 200, "url": ORIGIN + path, "body": "<html><main>Politica</main></html>"}
                if path.startswith("/?s="):
                    return {"status": 200, "url": ORIGIN + path, "body": "<html><main>Busca</main></html>"}
                if path == "/lpv-audit-7f1c9b/":
                    return {"status": 404, "url": ORIGIN + path, "body": "<html><main>404</main></html>"}
                if path.startswith("/wp-json/wp/v2/posts"):
                    return {"status": 200, "url": ORIGIN + path, "body": "[]"}
                row = next(item for item in ROWS if item["url"] == path)
                return {"status": 200, "url": row["canonical"], "body": production_document(row)}

        report = audit(Reader())
        self.assertEqual(report["status"], "APROVADO")
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["forms_sent"], 0)

    def test_l_and_p_has_no_artificial_translation(self):
        row = next(item for item in ROWS if item["id"] == 255)
        self.assertEqual(set(row["alternates"]), {"pt-BR", "x-default"})


class BackupAndDeploymentTests(unittest.TestCase):
    def test_private_backup_manifest_and_gzip(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            state = b'{"pages":{}}\n'
            (folder / "wordpress-state.json").write_bytes(state)
            with gzip.open(folder / "database.sql.gz", "wb") as stream:
                stream.write(b"CREATE TABLE `fixture` (`id` int);\n")
            files = {path.name: sha256_bytes(path.read_bytes()) for path in folder.iterdir()}
            (folder / "manifest.json").write_text(json.dumps({"files": files}), encoding="utf-8")
            self.assertEqual(validate_backup(folder)["status"], "APROVADO")
            (folder / "wordpress-state.json").write_text("changed", encoding="utf-8")
            self.assertEqual(validate_backup(folder)["status"], "BLOQUEADOR")

    def test_exact_authorization_is_required_before_any_io(self):
        with self.assertRaisesRegex(RuntimeError, "Exact human authorization"):
            execute(Path("does-not-exist"), "wrong phrase")
        self.assertEqual(AUTHORIZATION, "DEPLOY LPV PRODUCAO")

    def test_identity_validation_and_payload_cover_22_pages(self):
        pages = {}
        for row in ROWS:
            content = "old " + str(row["id"])
            pages[str(row["id"])] = {
                "exists": True, "post_type": "page", "path": row["url"],
                "content": content, "content_sha256": sha256_bytes(content.encode()),
            }
        state = {"home": ORIGIN, "siteurl": ORIGIN, "template": "twentytwentyfive",
                 "options": {"show_on_front": "page", "page_on_front": 7}, "pages": pages}
        self.assertEqual(state_identity_failures(state), [])
        payload = make_content_payload(state)
        self.assertEqual(len(payload["pages"]), 22)
        self.assertTrue(all(item["target_file"].startswith("package/html/") for item in payload["pages"]))

    def test_versioned_helpers_use_native_apis_and_no_direct_sql_writes(self):
        deployer = (ROOT / "scripts/deploy_production.py").read_text(encoding="utf-8")
        content = (ROOT / "wordpress/deploy/apply-content.php").read_text(encoding="utf-8")
        css = (ROOT / "wordpress/deploy/apply-css.php").read_text(encoding="utf-8")
        self.assertIn("wp_update_post", content)
        self.assertIn("wp_update_custom_css_post", css)
        self.assertIn("/wp-json/wp/v2/pages/", deployer)
        self.assertIn("application-password", deployer)
        self.assertNotIn("$wpdb", content + css)
        self.assertNotIn("wp db query", deployer)
        self.assertNotIn("formsubmit.co", deployer.lower())
        self.assertNotIn("debugview", deployer.lower())

    def test_helper_protocol_ignores_output_noise_and_prevents_css_false_negative(self):
        output = b"non-structured plugin notice\nLPV_RESULT:{\"status\":\"APROVADO\",\"changed\":false}\n"
        self.assertEqual(parse_helper_result(output), {"status": "APROVADO", "changed": False})
        with self.assertRaisesRegex(RuntimeError, "marker was not found"):
            parse_helper_result(b"notice without result")
        css = (ROOT / "wordpress/deploy/apply-css.php").read_text(encoding="utf-8")
        self.assertIn("'changed' => false", css)
        self.assertIn("LPV_RESULT:", css)

    def test_primary_failure_survives_perfect_rollback(self):
        primary = ValueError("original checkpoint failure")
        failure = failure_with_rollback(primary, lambda: {"status": "APROVADO", "exceptions": []})
        self.assertEqual(failure.primary_exception["type"], "ValueError")
        self.assertIn("original checkpoint failure", failure.primary_exception["message"])
        self.assertEqual(failure.rollback_result["status"], "APROVADO")

    def test_primary_failure_survives_rollback_failure(self):
        primary = ValueError("original checkpoint failure")

        def broken_rollback():
            raise RuntimeError("secondary rollback failure")

        failure = failure_with_rollback(primary, broken_rollback)
        self.assertEqual(failure.primary_exception["type"], "ValueError")
        self.assertEqual(failure.rollback_result["status"], "FALHOU")
        self.assertEqual(failure.rollback_result["exceptions"][0]["type"], "RuntimeError")

    def test_multiple_rollback_exceptions_remain_separate(self):
        rollback = {"status": "PARCIAL", "exceptions": [
            exception_record(RuntimeError("css")), exception_record(ValueError("plugin"))]}
        failure = failure_with_rollback(KeyError("primary"), lambda: rollback)
        self.assertEqual(failure.primary_exception["type"], "KeyError")
        self.assertEqual([item["type"] for item in failure.rollback_result["exceptions"]],
                         ["RuntimeError", "ValueError"])

    def test_maintenance_deactivation_is_in_execute_finally(self):
        source = (ROOT / "scripts/deploy_production.py").read_text(encoding="utf-8")
        execute_source = source[source.index("def execute("):source.index("def main(")]
        self.assertIn("finally:", execute_source)
        self.assertIn('wp(["maintenance-mode", "deactivate"', execute_source)

    def test_application_password_revocation_is_attempted_after_rest_failure(self):
        credential = {"uuid": "fixture", "secret": "never-written", "user": "fixture"}
        with patch.object(deploy_production, "application_password", return_value=credential), \
             patch.object(deploy_production, "rest_request", side_effect=RuntimeError("REST failed")), \
             patch.object(deploy_production, "revoke_application_password") as revoke:
            with self.assertRaisesRegex(RuntimeError, "REST failed"):
                apply_seo({"admin_user_login": "fixture", "pages": {}})
            revoke.assert_called_once_with(credential)


if __name__ == "__main__":
    unittest.main()
