import gzip
import html
import json
import secrets
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from scripts.audit_production import ORIGIN, audit, classify_baseline
from scripts.backup_production import validate_backup
from scripts import deploy_production
from scripts.deploy_production import (AUTHORIZATION, apply_seo,
                                       deactivate_native_maintenance_if_needed,
                                       exception_record, execute, failure_with_rollback,
                                       http_response, make_content_payload, new_journal,
                                       parse_helper_result, remove_deploy_shield,
                                       reconcile_journal, render_deploy_shield, rest_request, rollback,
                                       state_identity_failures)
from scripts.production_common import PACKAGE, ROOT, load_metadata, load_pages, sha256_bytes

ROWS = load_pages()
META = load_metadata()


class ShieldedRestFixture(BaseHTTPRequestHandler):
    deploy_token = "fixture-deploy-token"
    aioseo = {"title": "Before", "description": "Before"}

    def log_message(self, _format, *_args):
        pass

    def send_json(self, status, value):
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def authorize(self):
        if self.headers.get("X-LPV-Deploy-Token") != self.deploy_token:
            self.send_json(503, {"code": "service_unavailable"})
            return False
        if not self.headers.get("Authorization", "").startswith("Basic "):
            self.send_json(401, {"code": "rest_not_logged_in"})
            return False
        return True

    def do_GET(self):
        if not self.authorize():
            return
        self.send_json(200, {"id": ROWS[0]["id"], "aioseo_meta_data": self.aioseo})

    def do_POST(self):
        if not self.authorize():
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        self.__class__.aioseo = payload["aioseo_meta_data"]
        self.send_json(200, {"id": ROWS[0]["id"], "aioseo_meta_data": self.aioseo})


def production_document(row):
    content = (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_text(encoding="utf-8")
    head = f'<title>{html.escape(META[row["id"]]["title"])}</title>'
    head += '<meta name="description" content="' + html.escape(META[row["id"]]["description"], quote=True) + '">'
    head += f'<link rel="canonical" href="{row["canonical"]}">'
    head += ''.join(f'<link rel="alternate" hreflang="{language}" href="{url}">' for language, url in row["alternates"].items())
    return (f'<html lang="{row["lang"]}"><head>{head}<!-- aioseo --></head><body><main>'
            f'<div class="wp-block-post-content">{content}</div></main></body></html>')


class ProductionAuditTests(unittest.TestCase):
    def test_preexisting_target_differences_do_not_block_baseline(self):
        strict = {
            "status": "BLOQUEADOR",
            "blockers": ["page:7:single_h1", "page:7:lang"],
            "pages": [{"id": 7, "checks": {
                "http_200": "APROVADO", "single_h1": "BLOQUEADOR",
                "lang": "BLOQUEADOR", "aioseo_present": "APROVADO",
                "yoast_absent": "APROVADO",
            }}],
            "privacy": {}, "search": {}, "not_found": {},
            "sample_post": {"status": "NAO TESTADO"},
        }
        baseline = classify_baseline(strict)
        self.assertEqual(baseline["status"], "APROVADO")
        self.assertEqual(baseline["baseline_operational_safety"]["blocker_count"], 0)
        self.assertEqual(baseline["baseline_target_differences"]["status"], "EXPECTED_CHANGE")
        self.assertEqual(baseline["pages"][0]["checks"]["single_h1"], "EXPECTED_CHANGE")

    def test_real_operational_baseline_failures_still_block(self):
        strict = {
            "status": "BLOQUEADOR",
            "blockers": ["page:7:http_200", "page:7:aioseo_present", "privacy:http_200"],
            "pages": [{"id": 7, "checks": {
                "http_200": "BLOQUEADOR", "single_h1": "APROVADO",
                "aioseo_present": "BLOQUEADOR", "yoast_absent": "APROVADO",
            }}],
            "privacy": {"http_200": "BLOQUEADOR"}, "search": {}, "not_found": {},
            "sample_post": {"status": "NAO TESTADO"},
        }
        baseline = classify_baseline(strict)
        self.assertEqual(baseline["status"], "BLOQUEADOR")
        self.assertEqual(baseline["baseline_operational_safety"]["blocker_count"], 3)
        self.assertEqual(baseline["baseline_target_differences"]["status"], "NO_CHANGE")

    def test_baseline_classification_does_not_relax_postdeploy_report(self):
        strict = {
            "status": "BLOQUEADOR", "blockers": ["page:7:rendered_content_preserved"],
            "pages": [{"id": 7, "checks": {"rendered_content_preserved": "BLOQUEADOR"}}],
            "privacy": {}, "search": {}, "not_found": {},
            "sample_post": {"status": "NAO TESTADO"},
        }
        baseline = classify_baseline(strict)
        self.assertEqual(baseline["status"], "APROVADO")
        self.assertEqual(strict["status"], "BLOQUEADOR")
        self.assertEqual(strict["pages"][0]["checks"]["rendered_content_preserved"],
                         "BLOQUEADOR")
        self.assertEqual(baseline["post_deploy_acceptance"]["blocker_count"], 1)

    def test_executor_keeps_strict_postdeploy_audit(self):
        source = (ROOT / "scripts/deploy_production.py").read_text(encoding="utf-8")
        execute_source = source[source.index("def execute("):source.index("def main(")]
        self.assertIn("post = audit(ProductionReader(), stored_pages=", execute_source)
        self.assertNotIn("baseline_audit", execute_source)

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

        stored = {}
        for row in ROWS:
            content = (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_text(encoding="utf-8")
            stored[str(row["id"])] = {"exists": True, "content": content}
        report = audit(Reader(), stored_pages=stored)
        self.assertEqual(report["status"], "APROVADO")
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["forms_sent"], 0)
        for page in report["pages"]:
            for check in ("stored_content_preserved", "rendered_content_preserved",
                          "stored_image_urls_preserved",
                          "rendered_primary_image_urls_preserved",
                          "derived_image_urls_valid"):
                self.assertEqual(page["checks"][check], "APROVADO")

    def test_wpautop_script_corruption_remains_a_real_render_blocker(self):
        row = ROWS[0]
        content = (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_text(encoding="utf-8")
        corrupted = content.replace("  }\n\n  const language", "  }</p>\n<p>  const language", 1)
        from scripts.content_fidelity import compare_rendered_content
        result = compare_rendered_content(content, corrupted)
        self.assertFalse(result["preserved"])
        self.assertIn("scripts", result["failures"])

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

    def test_dry_run_names_all_five_fidelity_contracts(self):
        source = (ROOT / "scripts/deploy_production.py").read_text(encoding="utf-8")
        for check in ("stored_content_preserved", "rendered_content_preserved",
                      "stored_image_urls_preserved", "rendered_primary_image_urls_preserved",
                      "derived_image_urls_valid"):
            self.assertIn(check, source)

    def test_page_template_upgrade_accepts_only_the_approved_previous_archive(self):
        slug = "lpv-page-templates"
        previous = deploy_production.local_plugin_inventory(
            slug, "lpv-page-templates-1.0.0.zip")
        with patch.object(deploy_production, "remote_plugin_inventory", return_value=previous):
            self.assertTrue(deploy_production.plugin_matches_previous_approved(slug))
        with patch.object(deploy_production, "remote_plugin_inventory", return_value={"unknown.php": "bad"}):
            self.assertFalse(deploy_production.plugin_matches_previous_approved(slug))

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

    def test_native_maintenance_is_not_the_deploy_gate(self):
        source = (ROOT / "scripts/deploy_production.py").read_text(encoding="utf-8")
        execute_source = source[source.index("def execute("):source.index("def main(")]
        self.assertNotIn('wp(["maintenance-mode", "activate"', execute_source)
        self.assertIn("finally:", execute_source)
        self.assertIn("remove_deploy_shield()", execute_source)

    def test_native_maintenance_already_off_is_idempotent(self):
        completed = type("Result", (), {"returncode": 1})()
        with patch.object(deploy_production, "wp", return_value=completed) as command:
            result = deactivate_native_maintenance_if_needed()
        self.assertTrue(result["already_off"])
        self.assertEqual(command.call_count, 1)

    def test_shield_render_uses_hash_expiration_and_no_plaintext_token(self):
        token = secrets.token_urlsafe(32)
        rendered, expires_at = render_deploy_shield(token, now=100)
        self.assertEqual(expires_at, 100 + deploy_production.SHIELD_TTL_SECONDS)
        self.assertNotIn(token.encode(), rendered)
        self.assertNotIn(b"__LPV_DEPLOY_", rendered)
        self.assertIn(sha256_bytes(token.encode()).encode(), rendered)

    def test_shield_removal_is_idempotent(self):
        completed = type("Result", (), {"returncode": 0})()
        with patch.object(deploy_production, "remote", return_value=completed) as command:
            self.assertTrue(remove_deploy_shield()["already_absent_ok"])
            self.assertTrue(remove_deploy_shield()["already_absent_ok"])
        self.assertEqual(command.call_count, 2)

    def test_empty_aioseo_journal_is_not_required_during_rollback(self):
        state = {"pages": {}, "plugins": {}}
        with patch.object(deploy_production, "validate_backup", return_value={"status": "APROVADO"}), \
             patch.object(deploy_production, "load_json", return_value=state), \
             patch.object(deploy_production, "upload"), \
             patch.object(deploy_production, "remove_deploy_shield", return_value={"removed": True}):
            result = rollback(Path("fixture"), audit_after=False, journal=new_journal(),
                              remote_dir="/home/u504635074/.lpv-deploy/fixture")
        self.assertEqual(result["status"], "APROVADO")
        self.assertEqual(result["components"]["aioseo"]["status"], "NOT REQUIRED")

    def test_journal_reconciliation_captures_unacknowledged_remote_writes(self):
        journal = new_journal()
        journal["content_changed_ids"] = [7]
        observed = new_journal()
        observed["css_changed"] = True
        observed["content_changed_ids"] = [7, 17]
        observed["aioseo_changed_ids"] = [7]
        observed["template_plugin_changed"] = True
        with patch.object(deploy_production, "observed_journal", return_value=observed):
            result = reconcile_journal(journal, {})
        self.assertTrue(result["css_changed"])
        self.assertTrue(result["template_plugin_changed"])
        self.assertEqual(result["content_changed_ids"], [7, 17])
        self.assertEqual(result["aioseo_changed_ids"], [7])

    def test_rollback_refreshes_and_verifies_shield_before_restoring(self):
        state = {"admin_user_login": "fixture", "pages": {}, "plugins": {},
                 "custom_css": "before", "custom_css_sha256": sha256_bytes(b"before")}
        current = {"custom_css_sha256": sha256_bytes(b"after")}
        journal = new_journal()
        journal["css_changed"] = True
        credential = {"uuid": "fixture", "secret": "fixture", "user": "fixture"}
        with patch.object(deploy_production, "validate_backup", return_value={"status": "APROVADO"}), \
             patch.object(deploy_production, "load_json", return_value=state), \
             patch.object(deploy_production, "upload"), \
             patch.object(deploy_production, "application_password", return_value=credential), \
             patch.object(deploy_production, "install_deploy_shield") as install, \
             patch.object(deploy_production, "verify_deploy_shield", return_value={"frontend": 503}) as verify, \
             patch.object(deploy_production, "purge_litespeed_cache", return_value={"exit_code": 0}) as purge, \
             patch.object(deploy_production, "inspect_remote", return_value=current), \
             patch.object(deploy_production, "run_helper", return_value={"status": "APROVADO"}), \
             patch.object(deploy_production, "remove_deploy_shield", return_value={"removed": True}), \
             patch.object(deploy_production, "revoke_application_password",
                          return_value={"revoked": True}) as revoke:
            result = rollback(Path("fixture"), audit_after=False, journal=journal,
                              remote_dir="/home/u504635074/.lpv-deploy/fixture")
        self.assertEqual(result["status"], "APROVADO")
        install.assert_called_once()
        verify.assert_called_once()
        self.assertEqual(purge.call_count, 2)
        revoke.assert_called_once_with(credential)

    def test_shielded_aioseo_fixture_requires_both_credentials(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ShieldedRestFixture)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        credential = {"uuid": "fixture", "secret": "fixture-secret", "user": "fixture"}
        try:
            with patch.object(deploy_production, "ORIGIN", origin):
                self.assertEqual(http_response("/wp-json/wp/v2/pages/7")["status"], 503)
                self.assertEqual(http_response("/wp-json/wp/v2/pages/7",
                                               deploy_token="wrong")["status"], 503)
                self.assertEqual(http_response("/wp-json/wp/v2/pages/7",
                                               deploy_token=ShieldedRestFixture.deploy_token)["status"], 401)
                self.assertEqual(http_response("/wp-json/wp/v2/pages/7", credential=credential,
                                               deploy_token=ShieldedRestFixture.deploy_token)["status"], 200)
                page_id = ROWS[0]["id"]
                state = {"pages": {str(page_id): {"aioseo": {
                    "title": "Before", "description": "Before"}}}}
                journal = new_journal()
                result = apply_seo(state, credential, ShieldedRestFixture.deploy_token, journal,
                                   page_ids=[page_id])
                self.assertEqual(result["updated_ids"], [page_id])
                self.assertEqual(journal["aioseo_changed_ids"], [page_id])
                confirmed = rest_request(f"/wp-json/wp/v2/pages/{page_id}", credential,
                                         ShieldedRestFixture.deploy_token)
                self.assertEqual(confirmed["aioseo_meta_data"]["title"], META[page_id]["title"])
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_aioseo_restore_verifies_fresh_wp_cli_state_after_batch(self):
        page_ids = [ROWS[0]["id"], ROWS[1]["id"]]
        pages = {str(page_id): {"aioseo": {"title": "", "description": ""}}
                 for page_id in page_ids}
        state = {"pages": pages}
        current = {"pages": pages}
        journal = new_journal()
        credential = {"uuid": "fixture", "secret": "fixture", "user": "fixture"}
        with patch.object(deploy_production, "rest_request", return_value={}) as request, \
             patch.object(deploy_production, "inspect_remote", return_value=current) as inspect:
            result = apply_seo(state, credential, "fixture-token", journal,
                               restore=True, page_ids=page_ids)
        self.assertEqual(result["updated_ids"], page_ids)
        self.assertEqual(request.call_count, 2)
        inspect.assert_called_once_with()

    def test_application_password_and_shield_cleanup_are_in_execute_finally(self):
        source = (ROOT / "scripts/deploy_production.py").read_text(encoding="utf-8")
        execute_source = source[source.index("def execute("):source.index("def main(")]
        finally_source = execute_source[execute_source.rindex("finally:"):]
        self.assertIn("remove_deploy_shield()", finally_source)
        self.assertIn("revoke_application_password(credential)", finally_source)

    def test_partially_created_application_password_is_cleaned_up(self):
        created = type("Result", (), {"returncode": 0, "stdout": b"temporary-secret\n"})()
        broken_list = type("Result", (), {"returncode": 0, "stdout": b"not-json"})()
        cleanup_list = type("Result", (), {"returncode": 0,
                                            "stdout": b'[{"uuid":"fixture-uuid","app_id":"ignored"}]'})()
        deleted = type("Result", (), {"returncode": 0, "stdout": b""})()

        def fake_wp(arguments, **_kwargs):
            if arguments[2] == "create":
                fake_wp.app_id = next(value.split("=", 1)[1] for value in arguments if value.startswith("--app-id="))
                return created
            if arguments[2] == "list" and not hasattr(fake_wp, "cleanup"):
                fake_wp.cleanup = True
                return broken_list
            if arguments[2] == "list":
                cleanup_list.stdout = json.dumps([{"uuid": "fixture-uuid", "app_id": fake_wp.app_id}]).encode()
                return cleanup_list
            return deleted

        with patch.object(deploy_production, "wp", side_effect=fake_wp) as command:
            with self.assertRaises(json.JSONDecodeError):
                deploy_production.application_password("fixture")
        delete_calls = [call for call in command.call_args_list if call.args[0][2] == "delete"]
        self.assertEqual(len(delete_calls), 1)

    def test_deploy_error_removes_shield_and_revokes_application_password(self):
        backup = Path("fixture")
        state = {"admin_user_login": "fixture", "pages": {}, "plugins": {}}
        dry = {"status": "APROVADO", "backup": str(backup),
               "package_sha256": "package", "deployment_code_sha256": "code"}
        completed = type("Result", (), {"returncode": 1})()

        def fake_load(path):
            return dry if Path(path).name == "dry-run.json" else state

        credential = {"uuid": "fixture", "secret": "fixture-secret", "user": "fixture"}
        with patch.object(deploy_production, "load_json", side_effect=fake_load), \
             patch.object(deploy_production, "package_hash", return_value="package"), \
             patch.object(deploy_production, "deployment_code_hash", return_value="code"), \
             patch.object(deploy_production, "inspect_remote", return_value=state), \
             patch.object(deploy_production, "wp", return_value=completed), \
             patch.object(deploy_production, "ensure_remote_dir", return_value="/remote/fixture"), \
             patch.object(deploy_production, "upload"), \
             patch.object(deploy_production, "application_password", return_value=credential), \
             patch.object(deploy_production, "install_deploy_shield", return_value={"installed": True}), \
             patch.object(deploy_production, "purge_litespeed_cache", return_value={"exit_code": 0}), \
             patch.object(deploy_production, "verify_deploy_shield", side_effect=RuntimeError("fixture failure")), \
             patch.object(deploy_production, "rollback", return_value={"status": "APROVADO", "exceptions": []}), \
             patch.object(deploy_production, "remove_deploy_shield") as remove, \
             patch.object(deploy_production, "revoke_application_password") as revoke, \
             patch.object(deploy_production, "deploy_shield_exists", return_value=False), \
             patch.object(deploy_production, "attempt_event"), \
             patch.object(deploy_production, "cleanup_remote"):
            with self.assertRaises(deploy_production.DeploymentFailure) as raised:
                execute(backup, AUTHORIZATION)
        self.assertEqual(raised.exception.primary_exception["message"], "fixture failure")
        remove.assert_called_once_with()
        revoke.assert_called_once_with(credential)

    def test_token_is_redacted_from_exception_and_never_persisted_by_render(self):
        token = secrets.token_urlsafe(32)
        rendered, _ = render_deploy_shield(token)
        record = exception_record(RuntimeError("token=" + token))
        serialized = json.dumps(record)
        self.assertNotIn(token, serialized)
        self.assertNotIn(token.encode(), rendered)


if __name__ == "__main__":
    unittest.main()
