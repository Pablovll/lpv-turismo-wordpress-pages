#!/usr/bin/env python3
"""Dry-run, execute, or granularly roll back the controlled LPV deployment."""
import argparse
import base64
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
import zipfile
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
SHIELD_SOURCE = ROOT / "wordpress/deploy/lpv-deploy-shield.php"
SHIELD_REMOTE = WP_ROOT + "/wp-content/mu-plugins/lpv-deploy-shield.php"
SHIELD_TTL_SECONDS = 15 * 60


def new_journal():
    return {
        "template_plugin_changed": False,
        "language_plugin_changed": False,
        "css_changed": False,
        "content_changed_ids": [],
        "aioseo_changed_ids": [],
        "status_changed_ids": [],
        "deploy_shield_installed": False,
        "application_password_created": False,
        "cache_purged": False,
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


def render_deploy_shield(token, now=None):
    if not token or len(token) < 32:
        raise RuntimeError("Deploy shield token is not cryptographically adequate.")
    source = SHIELD_SOURCE.read_text(encoding="utf-8")
    if source.count("__LPV_DEPLOY_TOKEN_HASH__") != 1 or source.count("__LPV_DEPLOY_EXPIRES_AT__") != 1:
        raise RuntimeError("Deploy shield template placeholders are invalid.")
    expires_at = int(time.time() if now is None else now) + SHIELD_TTL_SECONDS
    rendered = source.replace("__LPV_DEPLOY_TOKEN_HASH__", sha256_bytes(token.encode("utf-8")))
    rendered = rendered.replace("__LPV_DEPLOY_EXPIRES_AT__", str(expires_at))
    if token in rendered:
        raise RuntimeError("Deploy shield plaintext token reached the rendered artifact.")
    return rendered.encode("utf-8"), expires_at


def local_plugin_inventory(slug):
    package = PACKAGE / "plugins" / f"{slug}-1.0.0.zip"
    inventory = {}
    with zipfile.ZipFile(package) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            parts = Path(item.filename).parts
            if len(parts) < 2 or parts[0] != slug:
                raise RuntimeError(f"Unexpected path in approved plugin archive: {slug}")
            inventory["/".join(parts[1:])] = sha256_bytes(archive.read(item))
    return inventory


def remote_plugin_inventory(slug):
    plugin_dir = f"{WP_ROOT}/wp-content/plugins/{slug}"
    command = (f"test -d {shlex.quote(plugin_dir)} && cd {shlex.quote(plugin_dir)} && "
               "find . -type f -print0 | sort -z | xargs -0 sha256sum")
    result = remote(command, check=False)
    if result.returncode != 0:
        return None
    inventory = {}
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        digest, path = line.split(None, 1)
        inventory[path.strip().removeprefix("./")] = digest
    return inventory


def plugin_matches_package(slug):
    return remote_plugin_inventory(slug) == local_plugin_inventory(slug)


def litespeed_cli_check():
    result = wp(["help", "litespeed-purge", "all", "--no-color"], check=False)
    output = (result.stdout + result.stderr).decode("utf-8", "replace")
    return {
        "registered": result.returncode == 0 and "wp litespeed-purge all" in output,
        "exit_code": result.returncode,
        "implementation": "official CLI subcommand; admin-ajax transport",
    }


def deactivate_native_maintenance_if_needed():
    active = wp(["maintenance-mode", "is-active", "--no-color"], check=False).returncode == 0
    if not active:
        return {"deactivated": True, "already_off": True}
    wp(["maintenance-mode", "deactivate", "--no-color"])
    still_active = wp(["maintenance-mode", "is-active", "--no-color"], check=False).returncode == 0
    if still_active:
        raise RuntimeError("Residual native WordPress maintenance mode could not be deactivated.")
    return {"deactivated": True, "already_off": False}


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
    litespeed_cli = litespeed_cli_check()
    if not litespeed_cli["registered"]: failures.append("litespeed_purge_cli_unavailable")
    if any("wordpress-seo" in name for name in plugins): failures.append("yoast_present")
    native_maintenance = wp(["maintenance-mode", "is-active", "--no-color"], check=False).returncode == 0
    if native_maintenance: failures.append("native_maintenance_active")
    residual_shield = deploy_shield_exists()
    if residual_shield: failures.append("residual_deploy_shield")
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
    plugin_package_matches = {}
    for slug in LPV_PLUGINS:
        plugin_package_matches[slug] = plugin_matches_package(slug)
        if not plugin_package_matches[slug]:
            failures.append(f"{slug}_installed_files_differ")
    shield_probe_token = "dry-run-only-" + "x" * 32
    rendered_shield, shield_expires_at = render_deploy_shield(shield_probe_token, now=0)
    shield_valid = (shield_probe_token.encode() not in rendered_shield and
                    b"__LPV_DEPLOY_" not in rendered_shield and
                    shield_expires_at == SHIELD_TTL_SECONDS)
    if not shield_valid: failures.append("deploy_shield_template_invalid")
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
        "deploy_shield": {
            "planned": True, "template_valid": shield_valid, "ttl_seconds": SHIELD_TTL_SECONDS,
            "frontend_expected": 503, "public_rest_expected": 503,
            "authorized_rest_requires": ["application_password", "ephemeral_header"],
            "removal_planned": True,
        },
        "plugin_package_matches": plugin_package_matches,
        "litespeed_purge": litespeed_cli,
        "native_maintenance_active": native_maintenance,
        "residual_deploy_shield": residual_shield,
        "planned_checkpoints": ["application_password", "deploy_shield", "shield_frontend_503",
                                "shield_public_rest_503", "shield_authorized_rest", "template_plugin",
                                "language_plugin", "css", "22_page_contents", "aioseo_rest",
                                "en_status", "litespeed_cache", "deploy_shield_removed",
                                "homepage_200", "public_audit", "application_password_revoked"],
        "rollback": {"journaled": True, "idempotent": True, "aioseo_empty_is_not_required": True},
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


def install_deploy_shield(remote_dir, token):
    rendered, expires_at = render_deploy_shield(token)
    descriptor, name = tempfile.mkstemp(prefix="lpv-deploy-shield-", suffix=".php")
    os.close(descriptor)
    local_file = Path(name)
    try:
        local_file.write_bytes(rendered)
        staged = remote_dir + "/lpv-deploy-shield.php"
        upload(local_file, staged)
        command = (f"mkdir -p {shlex.quote(WP_ROOT + '/wp-content/mu-plugins')} && "
                   f"install -m 600 {shlex.quote(staged)} {shlex.quote(SHIELD_REMOTE)} && "
                   f"test \"$(sha256sum {shlex.quote(SHIELD_REMOTE)} | cut -d' ' -f1)\" = "
                   f"{shlex.quote(sha256_bytes(rendered))}")
        remote(command)
    finally:
        local_file.unlink(missing_ok=True)
    return {"installed": True, "expires_at": expires_at, "sha256": sha256_bytes(rendered)}


def deploy_shield_exists():
    return remote(f"test -e {shlex.quote(SHIELD_REMOTE)}", check=False).returncode == 0


def remove_deploy_shield():
    result = remote(f"rm -f -- {shlex.quote(SHIELD_REMOTE)} && test ! -e {shlex.quote(SHIELD_REMOTE)}",
                    check=False)
    if result.returncode != 0:
        raise RuntimeError("Temporary deploy shield could not be removed.")
    return {"removed": True, "already_absent_ok": True}


def http_response(path, credential=None, deploy_token=None):
    headers = {"User-Agent": "LPV-Controlled-Deploy/2.0"}
    if credential:
        basic = base64.b64encode((credential["user"] + ":" + credential["secret"]).encode()).decode()
        headers["Authorization"] = "Basic " + basic
    if deploy_token:
        headers["X-LPV-Deploy-Token"] = deploy_token
    request = Request(ORIGIN + path, method="GET", headers=headers)
    try:
        with build_opener(ProxyHandler({}), NoRedirects()).open(request, timeout=30) as response:
            return {"status": response.status, "headers": dict(response.headers), "body": response.read()}
    except HTTPError as error:
        return {"status": error.code, "headers": dict(error.headers), "body": error.read()}
    except (URLError, TimeoutError) as error:
        raise RuntimeError("Deploy shield HTTP verification failed without logging credentials.") from error


def verify_deploy_shield(credential, deploy_token):
    frontend = http_response("/")
    public_rest = http_response("/wp-json/wp/v2/pages/7?context=edit&_fields=id")
    token_only = http_response("/wp-json/wp/v2/pages/7?context=edit&_fields=id",
                               deploy_token=deploy_token)
    authorized = http_response("/wp-json/wp/v2/pages/7?context=edit&_fields=id",
                               credential=credential, deploy_token=deploy_token)
    if frontend["status"] != 503:
        raise RuntimeError("Deploy shield did not return HTTP 503 for the public frontend.")
    if public_rest["status"] != 503:
        raise RuntimeError("Deploy shield did not return HTTP 503 for public REST.")
    if token_only["status"] not in (401, 403):
        raise RuntimeError("Deploy token without WordPress authentication obtained edit access.")
    if authorized["status"] != 200:
        raise RuntimeError("Authenticated deploy REST with the ephemeral token is unavailable.")
    retry_after = frontend["headers"].get("Retry-After") or frontend["headers"].get("retry-after")
    if retry_after != "120":
        raise RuntimeError("Deploy shield frontend response is missing Retry-After.")
    return {"frontend": 503, "public_rest": 503, "token_only": token_only["status"],
            "authorized_rest": 200, "retry_after": 120}


def make_content_payload(state, rollback=False, current=None, page_ids=None):
    items = []
    selected = set(page_ids) if page_ids is not None else None
    for row in load_pages():
        if selected is not None and row["id"] not in selected:
            continue
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


def activate_plugin(remote_dir, previous, slug, main_file, journal, journal_key, file_changes):
    existed = main_file in previous.get("plugins", {})
    was_active = previous.get("plugins", {}).get(main_file, {}).get("status") == "active"
    installed = wp(["plugin", "is-installed", slug, "--no-color"], check=False).returncode == 0
    files_replaced = False
    if installed and not plugin_matches_package(slug):
        journal[journal_key] = True
        file_changes[slug] = True
        wp(["plugin", "install", remote_dir + f"/package/plugins/{slug}-1.0.0.zip",
            "--force", "--no-color"])
        files_replaced = True
    elif not installed:
        journal[journal_key] = True
        file_changes[slug] = True
        wp(["plugin", "install", remote_dir + f"/package/plugins/{slug}-1.0.0.zip", "--no-color"])
        files_replaced = True
    active_before = wp(["plugin", "is-active", slug, "--no-color"], check=False).returncode == 0
    if not active_before:
        journal[journal_key] = True
        wp(["plugin", "activate", slug, "--no-color"])
    active_after = wp(["plugin", "is-active", slug, "--no-color"], check=False).returncode == 0
    version = wp(["plugin", "get", slug, "--field=version", "--no-color"]).stdout.decode().strip()
    if version != "1.0.0" or not active_after or not plugin_matches_package(slug):
        raise RuntimeError(f"Plugin checkpoint failed: {slug}")
    changed = files_replaced or active_after != was_active or not existed
    journal[journal_key] = journal[journal_key] or changed
    file_changes[slug] = files_replaced
    return {"changed": changed, "files_replaced": files_replaced, "reused_exact_files": not files_replaced}


def verify_plugin_runtime(remote_dir):
    runtime = wp(["eval-file", remote_dir + "/verify-runtime.php", "--no-color"])
    result = parse_helper_result(runtime.stdout)
    if result.get("status") != "APROVADO": raise RuntimeError("LPV runtime verification failed.")
    return result


def application_password(user_login):
    app_id = str(uuid.uuid4())
    name = "LPV Codex Deploy " + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    secret = ""
    record = None
    try:
        secret = wp(["user", "application-password", "create", "1", name,
                     "--app-id=" + app_id, "--porcelain", "--no-color"]).stdout.decode().strip()
        records = json.loads(wp(["user", "application-password", "list", "1",
                                 "--fields=uuid,app_id,name", "--format=json", "--no-color"]).stdout.decode())
        record = next((item for item in records if item.get("app_id") == app_id), None)
        if not secret or not record:
            raise RuntimeError("Temporary Application Password could not be identified.")
    except Exception:
        try:
            cleanup = wp(["user", "application-password", "list", "1",
                          "--fields=uuid,app_id", "--format=json", "--no-color"], check=False)
            if cleanup.returncode == 0:
                for item in json.loads(cleanup.stdout.decode()):
                    if item.get("app_id") == app_id:
                        wp(["user", "application-password", "delete", "1", item["uuid"], "--no-color"],
                           check=False)
        except Exception:
            pass
        raise
    return {"secret": secret, "uuid": record["uuid"], "name": name, "user": user_login}


def revoke_application_password(credential):
    if not credential:
        return {"revoked": True, "not_required": True}
    wp(["user", "application-password", "delete", "1", credential["uuid"], "--no-color"], check=False)
    records = json.loads(wp(["user", "application-password", "list", "1",
                             "--fields=uuid", "--format=json", "--no-color"]).stdout.decode())
    if any(item.get("uuid") == credential["uuid"] for item in records):
        raise RuntimeError("Temporary Application Password could not be revoked.")
    return {"revoked": True, "not_required": False}


def rest_request(path, credential, deploy_token, method="GET", payload=None):
    token = base64.b64encode((credential["user"] + ":" + credential["secret"]).encode()).decode()
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(ORIGIN + path, data=data, method=method,
                      headers={"Authorization": "Basic " + token, "Content-Type": "application/json",
                               "X-LPV-Deploy-Token": deploy_token,
                               "User-Agent": "LPV-Controlled-Deploy/1.0"})
    try:
        with build_opener(ProxyHandler({}), NoRedirects()).open(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("AIOSEO REST operation failed without logging credentials.") from error


def apply_seo(state, credential, deploy_token, journal, restore=False, page_ids=None):
    metadata = load_metadata()
    changed = []
    selected = set(page_ids) if page_ids is not None else None
    for row in load_pages():
        page_id = row["id"]
        if selected is not None and page_id not in selected:
            continue
        target = state["pages"][str(page_id)].get("aioseo", {}) if restore else metadata[page_id]
        values = {"title": target.get("title", ""), "description": target.get("description", "")}
        original = state["pages"][str(page_id)].get("aioseo", {})
        if not restore and original.get("title", "") == values["title"] and original.get("description", "") == values["description"]:
            continue
        rest_request(f"/wp-json/wp/v2/pages/{page_id}", credential, deploy_token, "POST",
                     {"aioseo_meta_data": values})
        changed.append(page_id)
        if not restore and page_id not in journal["aioseo_changed_ids"]:
            journal["aioseo_changed_ids"].append(page_id)
        if restore:
            continue
        result = rest_request(f"/wp-json/wp/v2/pages/{page_id}?" + urlencode(
            {"context": "edit", "_fields": "id,aioseo_meta_data"}), credential, deploy_token)
        actual = result.get("aioseo_meta_data", {})
        if actual.get("title", "") != values["title"] or actual.get("description", "") != values["description"]:
            raise RuntimeError(f"AIOSEO verification failed for page {page_id}")
    if restore and changed:
        current = inspect_remote()
        failures = []
        for page_id in changed:
            expected = state["pages"][str(page_id)].get("aioseo", {})
            actual = current["pages"][str(page_id)].get("aioseo", {})
            if (actual.get("title", "") != expected.get("title", "") or
                    actual.get("description", "") != expected.get("description", "")):
                failures.append(page_id)
        if failures:
            raise RuntimeError("AIOSEO rollback verification failed for page IDs: " +
                               ",".join(str(page_id) for page_id in failures))
    return {"updated_ids": changed}


def restore_plugins(backup, state, journal, file_changes):
    restored = []
    mappings = (("lpv-page-templates", "template_plugin_changed"),
                ("lpv-language-seo", "language_plugin_changed"))
    for slug, journal_key in mappings:
        if not journal[journal_key]:
            continue
        main_file = LPV_PLUGINS[slug]
        archive = Path(backup) / f"plugin-{slug}.tar.gz"
        original = state.get("plugins", {}).get(main_file)
        if file_changes.get(slug):
            wp(["plugin", "deactivate", slug, "--no-color"], check=False)
            wp(["plugin", "delete", slug, "--no-color"], check=False)
        if file_changes.get(slug) and archive.is_file():
            remote_archive = f"/home/u504635074/.lpv-{slug}-restore.tar.gz"
            upload(archive, remote_archive)
            remote(f"tar -C {WP_ROOT}/wp-content/plugins -xzf {remote_archive} && rm -f {remote_archive}")
        elif file_changes.get(slug) and not original:
            pass
        elif file_changes.get(slug):
            raise RuntimeError(f"Plugin backup is unavailable: {slug}.")
        if not original:
            wp(["plugin", "deactivate", slug, "--no-color"], check=False)
            wp(["plugin", "delete", slug, "--no-color"], check=False)
            if wp(["plugin", "is-installed", slug, "--no-color"], check=False).returncode == 0:
                raise RuntimeError(f"New plugin could not be removed during rollback: {slug}.")
            restored.append(slug)
            continue
        if original.get("status") == "active":
            wp(["plugin", "activate", slug, "--no-color"])
        else:
            wp(["plugin", "deactivate", slug, "--no-color"], check=False)
        active = wp(["plugin", "is-active", slug, "--no-color"], check=False).returncode == 0
        if active != (original.get("status") == "active"):
            raise RuntimeError(f"New plugin could not be removed during rollback: {slug}.")
        restored.append(slug)
    return {"restored": restored}


def purge_litespeed_cache():
    process = wp(["litespeed-purge", "all", "--no-color"], check=False)
    output = process.stdout + process.stderr
    if process.returncode != 0:
        raise RuntimeError("Official LiteSpeed purge command failed.")
    return {"exit_code": 0, "output_bytes": len(output), "output_sha256": sha256_bytes(output),
            "command": "wp litespeed-purge all"}


def observed_journal(state):
    current = inspect_remote()
    journal = new_journal()
    journal["css_changed"] = current["custom_css_sha256"] != state["custom_css_sha256"]
    journal["content_changed_ids"] = [row["id"] for row in load_pages()
                                               if current["pages"][str(row["id"])]["content_sha256"] !=
                                               state["pages"][str(row["id"])]["content_sha256"]]
    journal["aioseo_changed_ids"] = [row["id"] for row in load_pages()
                                              if current["pages"][str(row["id"])].get("aioseo", {}) !=
                                              state["pages"][str(row["id"])].get("aioseo", {})]
    journal["status_changed_ids"] = [row["id"] for row in load_pages()
                                             if current["pages"][str(row["id"])]["post_status"] !=
                                             state["pages"][str(row["id"])]["post_status"]]
    journal["template_plugin_changed"] = (
        current.get("plugins", {}).get(LPV_PLUGINS["lpv-page-templates"], {}).get("status") !=
        state.get("plugins", {}).get(LPV_PLUGINS["lpv-page-templates"], {}).get("status"))
    journal["language_plugin_changed"] = (
        current.get("plugins", {}).get(LPV_PLUGINS["lpv-language-seo"], {}).get("status") !=
        state.get("plugins", {}).get(LPV_PLUGINS["lpv-language-seo"], {}).get("status"))
    journal["deploy_shield_installed"] = deploy_shield_exists()
    return journal


def reconcile_journal(journal, state):
    observed = observed_journal(state)
    for key in ("template_plugin_changed", "language_plugin_changed", "css_changed",
                "deploy_shield_installed"):
        journal[key] = bool(journal[key] or observed[key])
    for key in ("content_changed_ids", "aioseo_changed_ids", "status_changed_ids"):
        journal[key] = sorted(set(journal[key]) | set(observed[key]))
    return journal


def rollback(backup, *, audit_after=True, journal=None, credential=None, deploy_token=None,
             remote_dir=None, file_changes=None):
    backup = Path(backup)
    if validate_backup(backup)["status"] != "APROVADO": raise RuntimeError("Rollback backup is invalid.")
    state = load_json(backup / "wordpress-state.json")
    journal = journal or observed_journal(state)
    file_changes = file_changes or {}
    own_remote_dir = remote_dir is None
    if own_remote_dir:
        remote_dir = ensure_remote_dir(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-rollback")
    own_credential = False
    deploy_token = deploy_token or secrets.token_urlsafe(32)
    report = {"status": "APROVADO", "exceptions": [], "components": {},
              "full_database_imported": False, "backup": str(backup), "journal": journal}

    def not_required(name):
        report["components"][name] = {"status": "NOT REQUIRED"}

    def restore_component(name, callback):
        try:
            report["components"][name] = {"status": "RESTORED", "result": callback()}
        except Exception as error:
            record = exception_record(error)
            record["component"] = name
            report["exceptions"].append(record)
            report["components"][name] = {"status": "FAILED"}

    public_changes = (journal["css_changed"] or journal["content_changed_ids"] or
                      journal["aioseo_changed_ids"] or journal["status_changed_ids"] or
                      journal["template_plugin_changed"] or journal["language_plugin_changed"])
    try:
        upload(ROOT / "wordpress/deploy/apply-content.php", remote_dir + "/apply-content.php")
        upload(ROOT / "wordpress/deploy/apply-css.php", remote_dir + "/apply-css.php")
        if public_changes and credential is None:
            credential = application_password(state["admin_user_login"])
            journal["application_password_created"] = True
            own_credential = True
        if public_changes:
            install_deploy_shield(remote_dir, deploy_token)
            journal["deploy_shield_installed"] = True
            restore_component("shield_cache", purge_litespeed_cache)
            restore_component("shield_verification", lambda: verify_deploy_shield(credential, deploy_token))

        if journal["content_changed_ids"]:
            def restore_content():
                current = inspect_remote()
                payload = make_content_payload(state, rollback=True, current=current,
                                               page_ids=journal["content_changed_ids"])
                return run_helper(remote_dir, "apply-content.php", payload) if payload["pages"] else {"changed": False}
            restore_component("content", restore_content)
        else:
            not_required("content")

        if journal["css_changed"]:
            def restore_css():
                current = inspect_remote()
                payload = {"expected_sha256": current["custom_css_sha256"],
                           "target_sha256": state["custom_css_sha256"],
                           "target_b64": base64.b64encode(state["custom_css"].encode()).decode()}
                return run_helper(remote_dir, "apply-css.php", payload)
            restore_component("css", restore_css)
        else:
            not_required("css")

        if journal["aioseo_changed_ids"]:
            restore_component("aioseo", lambda: apply_seo(
                state, credential, deploy_token, journal, restore=True,
                page_ids=journal["aioseo_changed_ids"]))
        else:
            not_required("aioseo")

        if journal["status_changed_ids"]:
            def restore_statuses():
                changed = []
                current = inspect_remote()
                for page_id in journal["status_changed_ids"]:
                    original = state["pages"][str(page_id)]["post_status"]
                    if current["pages"][str(page_id)]["post_status"] != original:
                        wp(["post", "update", str(page_id), "--post_status=" + original, "--no-color"])
                        changed.append(page_id)
                return {"updated_ids": changed}
            restore_component("statuses", restore_statuses)
        else:
            not_required("statuses")

        if journal["template_plugin_changed"] or journal["language_plugin_changed"]:
            restore_component("plugins", lambda: restore_plugins(backup, state, journal, file_changes))
        else:
            not_required("plugins")

        if public_changes:
            restore_component("cache", purge_litespeed_cache)
            if report["components"]["cache"]["status"] == "RESTORED":
                journal["cache_purged"] = True
        else:
            not_required("cache")
    finally:
        try:
            report["components"]["deploy_shield"] = {"status": "REMOVED", "result": remove_deploy_shield()}
        except Exception as error:
            record = exception_record(error)
            record["component"] = "deploy_shield"
            report["exceptions"].append(record)
            report["components"]["deploy_shield"] = {"status": "FAILED"}
        if own_credential:
            try:
                report["components"]["application_password"] = {
                    "status": "REVOKED", "result": revoke_application_password(credential)}
            except Exception as error:
                record = exception_record(error)
                record["component"] = "application_password"
                report["exceptions"].append(record)
        if own_remote_dir:
            cleanup_remote(remote_dir)
    report["status"] = "APROVADO" if not report["exceptions"] else "PARCIAL"
    dump_json(EVIDENCE / "rollback.json", report)
    if audit_after and not deploy_shield_exists():
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
    deactivate_native_maintenance_if_needed()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    journal = new_journal()
    attempt = new_attempt(run_id, backup)
    attempt["journal"] = journal
    attempt_event(attempt, "precheck", "COMPLETED", "validated dry-run, package and production fingerprint")
    remote_dir = ensure_remote_dir(run_id)
    checkpoints = []
    credential = None
    deploy_token = None
    file_changes = {}
    primary = None
    rollback_result = None
    cleanup_errors = []
    phase = "upload"
    try:
        attempt_event(attempt, phase, "STARTED", "upload approved package and versioned helpers")
        upload(PACKAGE, remote_dir + "/package")
        for name in ("apply-content.php", "apply-css.php", "verify-runtime.php"):
            upload(ROOT / "wordpress/deploy" / name, remote_dir + "/" + name)
        attempt_event(attempt, phase, "COMPLETED")

        phase = "application_password"
        credential = application_password(state["admin_user_login"])
        journal["application_password_created"] = True
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED")

        phase = "deploy_shield"
        deploy_token = secrets.token_urlsafe(32)
        shield_result = install_deploy_shield(remote_dir, deploy_token)
        journal["deploy_shield_installed"] = True
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=shield_result)
        shield_cache_result = purge_litespeed_cache()
        journal["cache_purged"] = True
        attempt_event(attempt, "deploy_shield_cache_prime", "COMPLETED", details=shield_cache_result)
        shield_checks = verify_deploy_shield(credential, deploy_token)
        attempt_event(attempt, "deploy_shield_checks", "COMPLETED", details=shield_checks)

        phase = "template_plugin"
        result = activate_plugin(remote_dir, state, "lpv-page-templates",
                                 LPV_PLUGINS["lpv-page-templates"], journal,
                                 "template_plugin_changed", file_changes)
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=result)

        phase = "language_plugin"
        result = activate_plugin(remote_dir, state, "lpv-language-seo",
                                 LPV_PLUGINS["lpv-language-seo"], journal,
                                 "language_plugin_changed", file_changes)
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=result)
        verify_plugin_runtime(remote_dir)

        target_css = (PACKAGE / "css/lpv-style.css").read_bytes()
        css_payload = {"expected_sha256": state["custom_css_sha256"],
                       "target_sha256": sha256_bytes(target_css),
                       "target_b64": base64.b64encode(target_css).decode()}
        phase = "css"
        css_result = run_helper(remote_dir, "apply-css.php", css_payload)
        journal["css_changed"] = bool(css_result.get("changed"))
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=css_result)

        phase = "content"
        content_result = run_helper(remote_dir, "apply-content.php", make_content_payload(state))
        journal["content_changed_ids"] = content_result.get("updated_ids", [])
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=content_result)

        phase = "aioseo"
        seo_result = apply_seo(state, credential, deploy_token, journal)
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=seo_result)

        phase = "en_publish"
        current = inspect_remote()
        for row in load_pages():
            if row["lang"] != "en":
                continue
            page = current["pages"][str(row["id"])]
            if page["path"] != row["url"]: raise RuntimeError("EN identity changed.")
            if page["post_status"] != "publish":
                wp(["post", "update", str(row["id"]), "--post_status=publish", "--no-color"])
                journal["status_changed_ids"].append(row["id"])
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details={"updated_ids": journal["status_changed_ids"]})

        phase = "cache"
        cache_result = purge_litespeed_cache()
        journal["cache_purged"] = True
        checkpoints.append(phase)
        attempt_event(attempt, phase, "COMPLETED", details=cache_result)

        phase = "deploy_shield_removal"
        shield_removal = remove_deploy_shield()
        attempt_event(attempt, phase, "COMPLETED", details=shield_removal)

        phase = "homepage_check"
        home = ProductionReader().get("/")
        if home.get("status") != 200:
            raise RuntimeError("Homepage is not HTTP 200 after deploy shield removal.")
        attempt_event(attempt, phase, "COMPLETED", details={"http_status": 200})

        phase = "public_audit"
        post = audit(ProductionReader())
        dump_json(EVIDENCE / "post-deploy.json", post)
        if post["status"] != "APROVADO":
            raise RuntimeError("Post-deploy audit contains blocking findings.")
        attempt_event(attempt, phase, "COMPLETED", details={"blockers": 0})
    except Exception as error:
        primary = error
        attempt["primary_exception"] = exception_record(error)
        attempt_event(attempt, phase, "FAILED", details=attempt["primary_exception"])
        reconciliation_error = None
        try:
            reconcile_journal(journal, state)
            attempt_event(attempt, "journal_reconciliation", "COMPLETED", details=journal)
        except Exception as journal_error:
            reconciliation_error = exception_record(journal_error)
            attempt_event(attempt, "journal_reconciliation", "FAILED", details=reconciliation_error)
        try:
            rollback_result = rollback(backup, journal=journal, credential=credential,
                                       deploy_token=deploy_token, remote_dir=remote_dir,
                                       file_changes=file_changes)
        except Exception as rollback_error:
            rollback_result = {"status": "FALHOU", "exceptions": [exception_record(rollback_error)]}
        if reconciliation_error:
            reconciliation_error["component"] = "journal_reconciliation"
            rollback_result.setdefault("exceptions", []).append(reconciliation_error)
            rollback_result["status"] = "PARCIAL"
        attempt["rollback"] = rollback_result
        attempt_event(attempt, "rollback", rollback_result.get("status", "FALHOU"), details=rollback_result)
    finally:
        try:
            remove_deploy_shield()
        except Exception as error:
            cleanup_errors.append(exception_record(error))
        try:
            revoke_application_password(credential)
        except Exception as error:
            cleanup_errors.append(exception_record(error))
        cleanup_remote(remote_dir)

    if deploy_shield_exists():
        cleanup_errors.append(exception_record(RuntimeError("Deploy shield remains installed.")))
    if cleanup_errors:
        if rollback_result is None:
            rollback_result = {"status": "PARCIAL", "exceptions": []}
        rollback_result.setdefault("exceptions", []).extend(cleanup_errors)
        rollback_result["status"] = "PARCIAL"
    if primary is not None:
        raise DeploymentFailure(exception_record(primary), rollback_result) from primary
    if cleanup_errors:
        raise RuntimeError("Critical deploy cleanup failed.")

    report = {"status": "APROVADO", "checkpoints": checkpoints, "rollback_executed": False,
              "journal": journal, "deploy_shield_removed": True,
              "temporary_credential_revoked": True, "backup": str(backup),
              "completed_at_utc": datetime.now(timezone.utc).isoformat()}
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
