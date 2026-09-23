#!/usr/bin/env python3
"""Dry-run, execute, or granularly roll back the controlled LPV deployment."""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

if __package__:
    from .audit_production import NoRedirects, ProductionReader, audit
    from .backup_production import validate_backup
    from .preflight_staging import package_preflight
    from .production_common import (BACKUPS, EVIDENCE, ORIGIN, PACKAGE, ROOT, SSH_ALIAS,
                                    WP_ROOT, approved_content, dump_json, inspect_remote,
                                    load_json, load_metadata, load_pages, remote, sha256_bytes, wp)
else:
    from audit_production import NoRedirects, ProductionReader, audit
    from backup_production import validate_backup
    from preflight_staging import package_preflight
    from production_common import (BACKUPS, EVIDENCE, ORIGIN, PACKAGE, ROOT, SSH_ALIAS,
                                   WP_ROOT, approved_content, dump_json, inspect_remote,
                                   load_json, load_metadata, load_pages, remote, sha256_bytes, wp)

AUTHORIZATION = "DEPLOY LPV PRODUCAO"
RESULT_PREFIX = "LPV_RESULT:"
LPV_PLUGINS = {
    "lpv-page-templates": "lpv-page-templates/lpv-page-templates.php",
    "lpv-language-seo": "lpv-language-seo/lpv-language-seo.php",
}


class DeploymentFailure(RuntimeError):
    """A primary deploy failure plus an independently recorded rollback result."""

    def __init__(self, primary_exception, rollback_result):
        self.primary_exception = primary_exception
        self.rollback_result = rollback_result
        super().__init__(f"DEPLOY FAILURE: {primary_exception['type']}: {primary_exception['message']}; "
                         f"ROLLBACK: {rollback_result.get('status', 'FALHOU')}")


class HelperProtocolError(RuntimeError):
    def __init__(self, message, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout_bytes = len(stdout)
        self.stderr_bytes = len(stderr)
        self.stdout_sha256 = sha256_bytes(stdout)
        self.stderr_sha256 = sha256_bytes(stderr)
        super().__init__(message)


def sanitize_error_text(value):
    text = str(value)
    text = re.sub(r"(?i)(authorization|password|secret|token)(\s*[:=]\s*)\S+", r"\1\2[redacted]", text)
    text = re.sub(r"(?i)basic\s+[A-Za-z0-9+/=]+", "Basic [redacted]", text)
    text = re.sub(r"(?i)(?:[A-Za-z0-9]{4}\s+){5}[A-Za-z0-9]{4}", "[redacted]", text)
    return text[:4000]


def exception_record(error):
    record = {
        "type": type(error).__name__,
        "message": sanitize_error_text(error),
        "exit_code": getattr(error, "returncode", None),
        "traceback": sanitize_error_text("".join(traceback.format_exception(error))),
    }
    for name in ("stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256"):
        if hasattr(error, name):
            record[name] = getattr(error, name)
    return record


def parse_helper_result(output):
    text = output.decode("utf-8", "replace") if isinstance(output, bytes) else str(output)
    for line in reversed(text.splitlines()):
        marker = line.find(RESULT_PREFIX)
        if marker >= 0:
            try:
                result = json.loads(line[marker + len(RESULT_PREFIX):])
            except json.JSONDecodeError as error:
                raise RuntimeError("LPV helper returned an invalid structured result.") from error
            if not isinstance(result, dict):
                raise RuntimeError("LPV helper result must be an object.")
            return result
    raise RuntimeError("LPV helper result marker was not found.")


def failure_with_rollback(primary, rollback_callable):
    primary_record = exception_record(primary)
    try:
        rollback_result = rollback_callable()
    except Exception as rollback_error:
        rollback_result = {
            "status": "FALHOU",
            "exceptions": [exception_record(rollback_error)],
        }
    return DeploymentFailure(primary_record, rollback_result)


def new_attempt(run_id, backup):
    return {
        "run_id": run_id, "backup": str(backup),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "events": [], "primary_exception": None, "rollback": None,
    }


def attempt_event(attempt, phase, status, operation=None, details=None):
    event = {"at_utc": datetime.now(timezone.utc).isoformat(), "phase": phase, "status": status}
    if operation: event["operation"] = operation
    if details is not None: event["details"] = details
    attempt["events"].append(event)
    dump_json(EVIDENCE / ("deploy-attempt-" + attempt["run_id"] + ".json"), attempt)


def latest_backup():
    candidates = sorted(path for path in BACKUPS.glob("*") if path.is_dir())
    if not candidates:
        raise RuntimeError("No private production backup is available.")
    return candidates[-1]


def package_hash():
    return sha256_bytes((PACKAGE.parent / "lpv-wordpress-stage-6.zip").read_bytes())


def deployment_code_hash():
    files = [ROOT / "scripts/deploy_production.py", ROOT / "scripts/production_common.py",
             ROOT / "scripts/audit_production.py", ROOT / "scripts/backup_production.py"]
    files.extend(sorted((ROOT / "wordpress/deploy").glob("*.php")))
    return sha256_bytes(b"".join(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes()
                                 for path in files))


def state_identity_failures(state):
    failures = []
    if state.get("home", "").rstrip("/") != ORIGIN or state.get("siteurl", "").rstrip("/") != ORIGIN:
        failures.append("production_origin")
    if state.get("template") != "twentytwentyfive": failures.append("active_theme")
    if state.get("options", {}).get("show_on_front") != "page": failures.append("show_on_front")
    if state.get("options", {}).get("page_on_front") != 7: failures.append("page_on_front")
    for row in load_pages():
        page = state.get("pages", {}).get(str(row["id"]), {})
        if not page.get("exists") or page.get("post_type") != "page" or page.get("path") != row["url"]:
            failures.append(f"page_{row['id']}_identity")
    return failures


def critical_fingerprint(state):
    return {
        "home": state.get("home"), "siteurl": state.get("siteurl"),
        "template": state.get("template"), "stylesheet": state.get("stylesheet"),
        "options": state.get("options"), "custom_css_sha256": state.get("custom_css_sha256"),
        "pages": {key: {
            "path": value.get("path"), "post_type": value.get("post_type"),
            "post_status": value.get("post_status"), "content_sha256": value.get("content_sha256"),
            "post_modified_gmt": value.get("post_modified_gmt"), "aioseo": value.get("aioseo"),
        } for key, value in state.get("pages", {}).items()},
        "plugins": state.get("plugins"), "wp_templates": state.get("wp_templates"),
        "aioseo_option_hashes": state.get("aioseo_option_hashes"),
    }


def dry_run(backup):
    backup = Path(backup)
    validation = validate_backup(backup)
    backup_state = load_json(backup / "wordpress-state.json")
    current = inspect_remote()
    failures = state_identity_failures(current)
    if validation["status"] != "APROVADO": failures.append("backup_invalid")
    if critical_fingerprint(current) != critical_fingerprint(backup_state):
        failures.append("production_changed_after_backup")
    package = package_preflight()
    if package["status"] != "APROVADO": failures.append("package_invalid")
    plugins = current.get("plugins", {})
    aioseo = plugins.get("all-in-one-seo-pack/all_in_one_seo_pack.php", {})
    litespeed = plugins.get("litespeed-cache/litespeed-cache.php", {})
    if aioseo.get("status") != "active" or not current.get("rest_aioseo_field"):
        failures.append("aioseo_rest_unavailable")
    if litespeed.get("status") != "active": failures.append("litespeed_inactive")
    if any("wordpress-seo" in name for name in plugins): failures.append("yoast_present")
    if any(template.get("slug") == "lpv-content-only" for template in current.get("wp_templates", [])):
        failures.append("template_database_override")
    baseline_path = EVIDENCE / "baseline.json"
    baseline = load_json(baseline_path) if baseline_path.is_file() else {}
    if not baseline: failures.append("baseline_missing")
    elif any(page["counts"].get("alternates", 0) for page in baseline.get("pages", [])):
        failures.append("existing_hreflang_emitter")
    metadata = load_metadata()
    content_changes, seo_changes, en_to_publish = [], [], []
    for row in load_pages():
        page = current["pages"][str(row["id"])]
        target = approved_content(row)
        if page["content_sha256"] != sha256_bytes(target.encode("utf-8")):
            content_changes.append(row["id"])
        desired = metadata[row["id"]]
        existing = page.get("aioseo", {})
        if existing.get("title", "") != desired["title"] or existing.get("description", "") != desired["description"]:
            seo_changes.append(row["id"])
        if row["lang"] == "en" and page["post_status"] != "publish":
            en_to_publish.append(row["id"])
    target_css = (PACKAGE / "css/lpv-style.css").read_bytes()
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run", "network_writes": 0, "backup": str(backup),
        "backup_validation": validation["status"], "package_sha256": package_hash(),
        "deployment_code_sha256": deployment_code_hash(),
        "wordpress_root": WP_ROOT,
        "versions": {"wordpress": current.get("wordpress_version"), "php": current.get("php_version"),
                     "theme": current.get("theme_version"), "aioseo": aioseo.get("version"),
                     "litespeed": litespeed.get("version")},
        "page_count": 22, "content_changes": content_changes,
        "content_change_count": len(content_changes),
        "css_change": current["custom_css_sha256"] != sha256_bytes(target_css),
        "current_css_sha256": current["custom_css_sha256"], "target_css_sha256": sha256_bytes(target_css),
        "aioseo_changes": seo_changes, "aioseo_change_count": len(seo_changes),
        "en_to_publish": en_to_publish, "en_publish_count": len(en_to_publish),
        "planned_checkpoints": ["maintenance", "template_plugin", "language_plugin", "css",
                                "22_page_contents", "aioseo_rest", "en_status", "litespeed_cache",
                                "maintenance_off", "public_audit"],
        "failures": sorted(set(failures)), "status": "APROVADO" if not failures else "BLOQUEADOR",
    }
    dump_json(EVIDENCE / "dry-run.json", report)
    return report


def ensure_remote_dir(run_id):
    path = f"/home/u504635074/.lpv-deploy/{run_id}"
    if not re.fullmatch(r"/home/u504635074/\.lpv-deploy/[A-Za-z0-9-]+", path):
        raise RuntimeError("Unsafe remote deployment path.")
    result = remote(f"umask 077 && mkdir -p {path}")
    return path


def upload(source, destination):
    command = ["scp", "-q"]
    if Path(source).is_dir(): command.append("-r")
    command.extend([str(source), f"{SSH_ALIAS}:{destination}"])
    subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def cleanup_remote(path):
    if not re.fullmatch(r"/home/u504635074/\.lpv-deploy/[A-Za-z0-9-]+", path):
        return
    check = remote(f"realpath {path}", check=False)
    if check.returncode == 0 and check.stdout.decode().strip() == path:
        remote(f"rm -rf -- {path}", check=False)


def make_content_payload(state, rollback=False, current=None):
    items = []
    for row in load_pages():
        page = state["pages"][str(row["id"])]
        approved = approved_content(row)
        original = page["content"]
        if rollback:
            current_page = (current or state)["pages"][str(row["id"])]
            approved_hash = sha256_bytes(approved.encode())
            if current_page["content_sha256"] == page["content_sha256"]:
                continue
            if current_page["content_sha256"] != approved_hash:
                raise RuntimeError(f"Unexpected content state during rollback: {row['id']}")
            items.append({"id": row["id"], "path": row["url"],
                          "expected_sha256": approved_hash,
                          "target_sha256": page["content_sha256"],
                          "target_b64": base64.b64encode(original.encode()).decode(),
                          "rollback_b64": base64.b64encode(approved.encode()).decode()})
        else:
            rel = "package/html/" + row["source"].removeprefix("pages/")
            items.append({"id": row["id"], "path": row["url"],
                          "expected_sha256": page["content_sha256"],
                          "target_sha256": sha256_bytes(approved.encode()), "target_file": rel,
                          "rollback_b64": base64.b64encode(original.encode()).decode()})
    return {"pages": items}


def run_helper(remote_dir, helper, payload):
    descriptor, name = tempfile.mkstemp(prefix="lpv-payload-", suffix=".json")
    os.close(descriptor)
    local_payload = Path(name)
    try:
        local_payload.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        upload(local_payload, remote_dir + "/payload.json")
        process = wp(["eval-file", remote_dir + "/" + helper, remote_dir + "/payload.json", "--no-color"],
                     check=False)
        try:
            result = parse_helper_result(process.stdout)
        except RuntimeError as error:
            raise HelperProtocolError(str(error), process.returncode,
                                      process.stdout, process.stderr) from error
        result["transport_exit_code"] = process.returncode
        result["transport_stdout_bytes"] = len(process.stdout)
        result["transport_stderr_bytes"] = len(process.stderr)
        result["transport_stdout_sha256"] = sha256_bytes(process.stdout)
        result["transport_stderr_sha256"] = sha256_bytes(process.stderr)
        if result.get("status") != "APROVADO":
            raise RuntimeError("LPV helper reported a blocking result.")
        return result
    finally:
        local_payload.unlink(missing_ok=True)


def install_plugins(remote_dir, previous):
    for slug, main_file in LPV_PLUGINS.items():
        zip_name = f"{slug}-1.0.0.zip"
        args = ["plugin", "install", remote_dir + "/package/plugins/" + zip_name, "--activate", "--no-color"]
        if main_file in previous.get("plugins", {}): args.insert(-1, "--force")
        wp(args)
        version = wp(["plugin", "get", slug, "--field=version", "--no-color"]).stdout.decode().strip()
        status = wp(["plugin", "is-active", slug, "--no-color"], check=False).returncode
        if version != "1.0.0" or status != 0:
            raise RuntimeError(f"Plugin checkpoint failed: {slug}")
    runtime = wp(["eval-file", remote_dir + "/verify-runtime.php", "--no-color"])
    result = parse_helper_result(runtime.stdout)
    if result.get("status") != "APROVADO": raise RuntimeError("LPV runtime verification failed.")


def application_password(user_login):
    app_id = str(uuid.uuid4())
    name = "LPV Codex Deploy " + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    secret = wp(["user", "application-password", "create", "1", name,
                 "--app-id=" + app_id, "--porcelain", "--no-color"]).stdout.decode().strip()
    records = json.loads(wp(["user", "application-password", "list", "1",
                             "--fields=uuid,app_id,name", "--format=json", "--no-color"]).stdout.decode())
    record = next((item for item in records if item.get("app_id") == app_id), None)
    if not secret or not record: raise RuntimeError("Temporary Application Password could not be identified.")
    return {"secret": secret, "uuid": record["uuid"], "name": name, "user": user_login}


def revoke_application_password(credential):
    if credential:
        wp(["user", "application-password", "delete", "1", credential["uuid"], "--no-color"], check=False)


def rest_request(path, credential, method="GET", payload=None):
    token = base64.b64encode((credential["user"] + ":" + credential["secret"]).encode()).decode()
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(ORIGIN + path, data=data, method=method,
                      headers={"Authorization": "Basic " + token, "Content-Type": "application/json",
                               "User-Agent": "LPV-Controlled-Deploy/1.0"})
    try:
        with build_opener(ProxyHandler({}), NoRedirects()).open(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("AIOSEO REST operation failed without logging credentials.") from error


def apply_seo(state, restore=False):
    metadata = load_metadata()
    credential = None
    changed = []
    try:
        credential = application_password(state["admin_user_login"])
        for row in load_pages():
            page_id = row["id"]
            target = state["pages"][str(page_id)].get("aioseo", {}) if restore else metadata[page_id]
            values = {"title": target.get("title", ""), "description": target.get("description", "")}
            rest_request(f"/wp-json/wp/v2/pages/{page_id}", credential, "POST",
                         {"aioseo_meta_data": values})
            result = rest_request(f"/wp-json/wp/v2/pages/{page_id}?" + urlencode(
                {"context": "edit", "_fields": "id,aioseo_meta_data"}), credential)
            actual = result.get("aioseo_meta_data", {})
            if actual.get("title", "") != values["title"] or actual.get("description", "") != values["description"]:
                raise RuntimeError(f"AIOSEO verification failed for page {page_id}")
            changed.append(page_id)
    except Exception:
        if not restore and credential:
            for page_id in reversed(changed):
                original = state["pages"][str(page_id)].get("aioseo", {})
                rest_request(f"/wp-json/wp/v2/pages/{page_id}", credential, "POST",
                             {"aioseo_meta_data": {"title": original.get("title", ""),
                                                   "description": original.get("description", "")}})
        raise
    finally:
        revoke_application_password(credential)
    return {"updated_ids": changed, "temporary_credential_revoked": True}


def restore_plugins(backup, state):
    for slug, main_file in LPV_PLUGINS.items():
        archive = Path(backup) / f"plugin-{slug}.tar.gz"
        wp(["plugin", "deactivate", slug, "--no-color"], check=False)
        wp(["plugin", "delete", slug, "--no-color"], check=False)
        if archive.is_file():
            remote_archive = f"/home/u504635074/.lpv-{slug}-restore.tar.gz"
            upload(archive, remote_archive)
            remote(f"tar -C {WP_ROOT}/wp-content/plugins -xzf {remote_archive} && rm -f {remote_archive}")
            if state.get("plugins", {}).get(main_file, {}).get("status") == "active":
                wp(["plugin", "activate", slug, "--no-color"])
            if wp(["plugin", "is-installed", slug, "--no-color"], check=False).returncode != 0:
                raise RuntimeError(f"Plugin restoration could not verify {slug}.")
        elif wp(["plugin", "is-installed", slug, "--no-color"], check=False).returncode == 0:
            raise RuntimeError(f"New plugin could not be removed during rollback: {slug}.")


def rollback(backup, *, audit_after=True, components=None):
    backup = Path(backup)
    if validate_backup(backup)["status"] != "APROVADO": raise RuntimeError("Rollback backup is invalid.")
    state = load_json(backup / "wordpress-state.json")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-rollback"
    remote_dir = ensure_remote_dir(run_id)
    components = set(components or ("plugins", "css", "content", "aioseo", "en_publish"))
    report = {
        "status": "APROVADO", "exceptions": [], "components": {},
        "full_database_imported": False, "backup": str(backup),
    }

    def restore_component(name, callback):
        try:
            result = callback()
            report["components"][name] = {"status": "RESTORED", "result": result}
        except Exception as error:
            record = exception_record(error)
            record["component"] = name
            report["exceptions"].append(record)
            report["components"][name] = {"status": "FAILED"}

    wp(["maintenance-mode", "activate", "--no-color"], check=False)
    try:
        upload(ROOT / "wordpress/deploy/apply-content.php", remote_dir + "/apply-content.php")
        upload(ROOT / "wordpress/deploy/apply-css.php", remote_dir + "/apply-css.php")
        if "content" in components:
            def restore_content():
                current = inspect_remote()
                payload = make_content_payload(state, rollback=True, current=current)
                return run_helper(remote_dir, "apply-content.php", payload) if payload["pages"] else {"changed": False}
            restore_component("content", restore_content)
        if "css" in components:
            def restore_css():
                css = state["custom_css"].encode()
                current = inspect_remote()
                css_payload = {"expected_sha256": current["custom_css_sha256"],
                               "target_sha256": state["custom_css_sha256"],
                               "target_b64": base64.b64encode(css).decode()}
                return run_helper(remote_dir, "apply-css.php", css_payload)
            restore_component("css", restore_css)
        if "aioseo" in components:
            restore_component("aioseo", lambda: apply_seo(state, restore=True))
        if "en_publish" in components:
            def restore_statuses():
                changed = []
                current = inspect_remote()
                for row in load_pages():
                    original = state["pages"][str(row["id"])]["post_status"]
                    if current["pages"][str(row["id"])]["post_status"] != original:
                        wp(["post", "update", str(row["id"]), "--post_status=" + original, "--no-color"])
                        changed.append(row["id"])
                return {"updated_ids": changed}
            restore_component("en_publish", restore_statuses)
        if "plugins" in components:
            restore_component("plugins", lambda: restore_plugins(backup, state))
        restore_component("cache", lambda: wp(["litespeed-purge", "all", "--no-color"]).returncode)
    finally:
        maintenance = wp(["maintenance-mode", "deactivate", "--no-color"], check=False)
        report["maintenance_deactivated"] = maintenance.returncode == 0
        if maintenance.returncode != 0:
            record = {"component": "maintenance", "type": "CommandError",
                      "message": "Maintenance mode could not be deactivated.",
                      "exit_code": maintenance.returncode, "traceback": ""}
            report["exceptions"].append(record)
        cleanup_remote(remote_dir)
    report["status"] = "APROVADO" if not report["exceptions"] else "PARCIAL"
    dump_json(EVIDENCE / "rollback.json", report)
    if audit_after:
        try:
            dump_json(EVIDENCE / "post-rollback.json", audit(ProductionReader()))
        except Exception as error:
            record = exception_record(error)
            record["component"] = "post_rollback_audit"
            report["exceptions"].append(record)
            report["status"] = "PARCIAL"
            dump_json(EVIDENCE / "rollback.json", report)
    return report


def execute(backup, authorization):
    if authorization != AUTHORIZATION: raise RuntimeError("Exact human authorization is required.")
    dry = load_json(EVIDENCE / "dry-run.json")
    if dry.get("status") != "APROVADO" or Path(dry.get("backup", "")) != Path(backup):
        raise RuntimeError("Approved dry-run for this backup is required.")
    if dry.get("package_sha256") != package_hash(): raise RuntimeError("Package changed after dry-run.")
    if dry.get("deployment_code_sha256") != deployment_code_hash():
        raise RuntimeError("Deployment code changed after dry-run.")
    state = load_json(Path(backup) / "wordpress-state.json")
    if critical_fingerprint(inspect_remote()) != critical_fingerprint(state):
        raise RuntimeError("Production changed after dry-run; create a new backup and dry-run.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = new_attempt(run_id, backup)
    attempt_event(attempt, "precheck", "COMPLETED", "validated dry-run, package and production fingerprint")
    remote_dir = ensure_remote_dir(run_id)
    checkpoints = []
    rollback_done = False
    phase = "maintenance"
    attempt_event(attempt, phase, "STARTED", "wp maintenance-mode activate")
    wp(["maintenance-mode", "activate", "--no-color"])
    attempt_event(attempt, phase, "COMPLETED")
    try:
        phase = "upload"
        attempt_event(attempt, phase, "STARTED", "upload approved package and versioned helpers")
        upload(PACKAGE, remote_dir + "/package")
        for name in ("apply-content.php", "apply-css.php", "verify-runtime.php"):
            upload(ROOT / "wordpress/deploy" / name, remote_dir + "/" + name)
        attempt_event(attempt, phase, "COMPLETED")
        phase = "plugins"
        attempt_event(attempt, phase, "STARTED", "install and verify both LPV plugins")
        checkpoints.append("plugins"); install_plugins(remote_dir, state)
        attempt_event(attempt, phase, "COMPLETED")
        target_css = (PACKAGE / "css/lpv-style.css").read_bytes()
        css_payload = {"expected_sha256": state["custom_css_sha256"],
                       "target_sha256": sha256_bytes(target_css),
                       "target_b64": base64.b64encode(target_css).decode()}
        phase = "css"
        attempt_event(attempt, phase, "STARTED", "wp_update_custom_css_post")
        checkpoints.append("css"); css_result = run_helper(remote_dir, "apply-css.php", css_payload)
        attempt_event(attempt, phase, "COMPLETED", details=css_result)
        phase = "content"
        attempt_event(attempt, phase, "STARTED", "wp_update_post for 22 approved pages")
        checkpoints.append("content"); content_result = run_helper(
            remote_dir, "apply-content.php", make_content_payload(state))
        attempt_event(attempt, phase, "COMPLETED", details=content_result)
        phase = "aioseo"
        attempt_event(attempt, phase, "STARTED", "official AIOSEO REST field")
        checkpoints.append("aioseo"); seo_result = apply_seo(state)
        attempt_event(attempt, phase, "COMPLETED", details=seo_result)
        phase = "en_publish"
        attempt_event(attempt, phase, "STARTED", "verify seven English statuses")
        checkpoints.append("en_publish")
        for row in load_pages():
            if row["lang"] == "en":
                page = inspect_remote()["pages"][str(row["id"])]
                if page["path"] != row["url"]: raise RuntimeError("EN identity changed.")
                if page["post_status"] != "publish":
                    wp(["post", "update", str(row["id"]), "--post_status=publish", "--no-color"])
        attempt_event(attempt, phase, "COMPLETED")
        phase = "cache"
        attempt_event(attempt, phase, "STARTED", "wp litespeed-purge all")
        wp(["litespeed-purge", "all", "--no-color"]); checkpoints.append("cache")
        attempt_event(attempt, phase, "COMPLETED")
    except Exception as primary:
        primary_record = exception_record(primary)
        attempt["primary_exception"] = primary_record
        attempt_event(attempt, phase, "FAILED", details=primary_record)
        failure = failure_with_rollback(primary, lambda: rollback(backup, components=checkpoints))
        rollback_done = True
        attempt["rollback"] = failure.rollback_result
        attempt_event(attempt, "rollback", failure.rollback_result.get("status", "FALHOU"),
                      details=failure.rollback_result)
        raise failure from primary
    finally:
        maintenance = wp(["maintenance-mode", "deactivate", "--no-color"], check=False)
        attempt_event(attempt, "maintenance", "DEACTIVATED" if maintenance.returncode == 0 else "DEACTIVATION_FAILED")
        cleanup_remote(remote_dir)
    home = ProductionReader().get("/")
    if home.get("status") != 200:
        primary = RuntimeError("Homepage is not HTTP 200 after maintenance mode.")
        attempt["primary_exception"] = exception_record(primary)
        failure = failure_with_rollback(primary, lambda: rollback(backup))
        attempt["rollback"] = failure.rollback_result
        attempt_event(attempt, "homepage_check", "FAILED", details=attempt["primary_exception"])
        raise failure from primary
    attempt_event(attempt, "homepage_check", "COMPLETED", details={"http_status": 200})
    post = audit(ProductionReader())
    dump_json(EVIDENCE / "post-deploy.json", post)
    if post["status"] != "APROVADO":
        primary = RuntimeError("Post-deploy audit contains blocking findings.")
        attempt["primary_exception"] = exception_record(primary)
        failure = failure_with_rollback(primary, lambda: rollback(backup))
        rollback_done = True
        attempt["rollback"] = failure.rollback_result
        attempt_event(attempt, "public_audit", "FAILED", details={"blockers": len(post["blockers"])})
        raise failure from primary
    attempt_event(attempt, "public_audit", "COMPLETED", details={"blockers": 0})
    report = {"status": "APROVADO", "checkpoints": checkpoints, "rollback_executed": rollback_done,
              "backup": str(backup), "completed_at_utc": datetime.now(timezone.utc).isoformat()}
    dump_json(EVIDENCE / "deployment.json", report)
    attempt["completed_at_utc"] = report["completed_at_utc"]
    attempt_event(attempt, "deployment", "APROVADO")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--authorization")
    args = parser.parse_args()
    backup = args.backup or latest_backup()
    try:
        if args.dry_run:
            result = dry_run(backup)
            print(f"Production dry-run: {result['status']}; {len(result['failures'])} blockers.")
            return 0 if result["status"] == "APROVADO" else 2
        if args.execute:
            result = execute(backup, args.authorization)
            print("Production deployment: " + result["status"])
            return 0
        result = rollback(backup)
        print("Production rollback: " + result["status"])
        return 0 if result["status"] == "APROVADO" else 2
    except Exception as error:
        print("BLOCKED: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
