#!/usr/bin/env python3
"""Offline package checks plus read-only LPV production compatibility checks."""
import argparse
import json
from pathlib import Path

if __package__:
    from .preflight_staging import git, package_preflight, repository_scan
    from .production_common import EVIDENCE, ORIGIN, WP_ROOT, dump_json, inspect_remote, load_pages
else:
    from preflight_staging import git, package_preflight, repository_scan
    from production_common import EVIDENCE, ORIGIN, WP_ROOT, dump_json, inspect_remote, load_pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVIDENCE / "preflight-production.json")
    args = parser.parse_args()
    failures = []
    package = package_preflight()
    sensitive = repository_scan()
    try:
        state = inspect_remote()
    except Exception:
        state = {}
        failures.append("remote_inventory_unavailable")
    if state:
        expected = {
            "home": ORIGIN, "siteurl": ORIGIN, "template": "twentytwentyfive",
            "show_on_front": "page", "page_on_front": 7,
        }
        for key in ("home", "siteurl", "template"):
            if state.get(key, "").rstrip("/") != expected[key].rstrip("/"):
                failures.append(key)
        for key in ("show_on_front", "page_on_front"):
            if state.get("options", {}).get(key) != expected[key]:
                failures.append(key)
        version = tuple(int(part) for part in state.get("wordpress_version", "0").split(".")[:2])
        php_version = tuple(int(part) for part in state.get("php_version", "0").split(".")[:2])
        if version < (6, 7): failures.append("wordpress_version")
        if php_version < (7, 4): failures.append("php_version")
        plugins = state.get("plugins", {})
        if plugins.get("all-in-one-seo-pack/all_in_one_seo_pack.php", {}).get("status") != "active":
            failures.append("aioseo_inactive")
        if plugins.get("litespeed-cache/litespeed-cache.php", {}).get("status") != "active":
            failures.append("litespeed_inactive")
        if any("wordpress-seo" in name for name in plugins):
            failures.append("yoast_present")
        if not state.get("rest_aioseo_field"):
            failures.append("aioseo_rest_write_field_missing")
        if any(template.get("slug") == "lpv-content-only" for template in state.get("wp_templates", [])):
            failures.append("lpv_content_only_database_override")
        for row in load_pages():
            page = state.get("pages", {}).get(str(row["id"]), {})
            if not page.get("exists") or page.get("post_type") != "page" or page.get("path") != row["url"]:
                failures.append(f"page_{row['id']}_identity")
    report = {
        "git_status": git("status", "--short", "--branch").decode().splitlines(),
        "package": package, "sensitive_data": sensitive,
        "remote": {
            "status": "BLOQUEADOR" if failures else "APROVADO",
            "wordpress_root": WP_ROOT, "checks": len(load_pages()), "failures": failures,
            "versions": {key: state.get(key) for key in ("wordpress_version", "php_version", "theme_version")},
        },
        "network_writes": 0,
    }
    dump_json(args.output, report)
    blocked = package["status"] != "APROVADO" or sensitive["status"] != "APROVADO" or bool(failures)
    print(f"Production preflight: {'BLOQUEADOR' if blocked else 'APROVADO'}; report written.")
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
