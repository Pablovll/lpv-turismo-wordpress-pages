#!/usr/bin/env python3
"""Read-only LPV production audit. Requires an explicit production gate."""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from bs4 import BeautifulSoup

if __package__:
    from .content_fidelity import (compare_rendered_content, compare_rendered_images,
                                   compare_stored_content)
else:
    from content_fidelity import (compare_rendered_content, compare_rendered_images,
                                  compare_stored_content)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "publication/stage-6"
ORIGIN = "https://lpvturismo.com"
MAX_BYTES = 5 * 1024 * 1024
BASELINE_OPERATIONAL_PAGE_CHECKS = {
    "http_200", "expected_url_no_redirect", "aioseo_present", "yoast_absent",
}


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ProductionReader:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirects())
        self.image_probes = {}

    def get(self, path):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Production audit accepts root-relative paths only.")
        request = Request(ORIGIN + path, headers={
            "User-Agent": "LPV-Production-ReadOnly-Audit/1.0",
            "Accept": "text/html,application/json;q=0.9",
        }, method="GET")
        try:
            try:
                response = self.opener.open(request, timeout=30)
            except HTTPError as error:
                response = error
            with response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    return {"status": 0, "url": response.url, "error": "response_size_limit"}
                return {"status": response.status, "url": response.url,
                        "body": body.decode("utf-8"), "headers": dict(response.headers.items())}
        except (URLError, TimeoutError, OSError, UnicodeError):
            return {"status": 0, "error": "request_failed_no_sensitive_details_logged"}

    def probe_image(self, url):
        if url in self.image_probes:
            return self.image_probes[url]
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "lpvturismo.com"
                or parsed.username or parsed.password or parsed.fragment
                or not parsed.path.startswith("/wp-content/uploads/")):
            result = {"url": sanitized_resource_url(url), "http_status": None,
                      "content_type": "", "redirect": None,
                      "error": "policy_rejected", "reachable": False}
            self.image_probes[url] = result
            return result
        request_url = urlunsplit((parsed.scheme, parsed.netloc, quote(parsed.path, safe="/%:@"),
                                  parsed.query, ""))
        request = Request(request_url, headers={
            "User-Agent": "LPV-Production-ReadOnly-Audit/1.0",
            "Accept": "image/*",
            "Range": "bytes=0-0",
        }, method="GET")
        try:
            try:
                response = self.opener.open(request, timeout=20)
            except HTTPError as error:
                response = error
            with response:
                status = response.status
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                location = response.headers.get("Location")
                result = {
                    "url": sanitized_resource_url(url),
                    "http_status": status,
                    "content_type": content_type,
                    "redirect": sanitized_resource_url(location) if location else None,
                    "error": "http_error" if status >= 400 else ("redirect" if 300 <= status < 400 else None),
                    "reachable": status in (200, 206) and content_type.startswith("image/"),
                }
        except TimeoutError:
            result = {"url": sanitized_resource_url(url), "http_status": None,
                      "content_type": "", "redirect": None,
                      "error": "timeout", "reachable": False}
        except URLError as error:
            kind = "timeout" if isinstance(getattr(error, "reason", None), TimeoutError) else "network_error"
            result = {"url": sanitized_resource_url(url), "http_status": None,
                      "content_type": "", "redirect": None,
                      "error": kind, "reachable": False}
        except (OSError, UnicodeError):
            result = {"url": sanitized_resource_url(url), "http_status": None,
                      "content_type": "", "redirect": None,
                      "error": "network_error", "reachable": False}
        self.image_probes[url] = result
        return result


def sanitized_resource_url(url):
    if not url:
        return ""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, host + port, parsed.path, "", ""))


def normalized_probe_result(url, result):
    if isinstance(result, int):
        return {"url": sanitized_resource_url(url), "http_status": result,
                "content_type": "image/unknown" if result in (200, 206) else "",
                "redirect": None, "error": None if result in (200, 206) else "http_error",
                "reachable": result in (200, 206)}
    normalized = {"url": sanitized_resource_url(url), "http_status": None,
                  "content_type": "", "redirect": None,
                  "error": "unknown_probe_failure", "reachable": False}
    normalized.update(result)
    normalized["url"] = sanitized_resource_url(normalized.get("url") or url)
    if normalized.get("redirect"):
        normalized["redirect"] = sanitized_resource_url(normalized["redirect"])
    return normalized


def state(condition):
    return "APROVADO" if condition else "BLOQUEADOR"


def inspect_page(row, metadata, response, stored_page=None, image_probe=None):
    soup = BeautifulSoup(response.get("body", ""), "html.parser")
    checks = {
        "http_200": state(response.get("status") == 200),
        "expected_url_no_redirect": state(response.get("url") == row["canonical"]),
        "single_main": state(len(soup.select("main")) == 1),
        "single_h1": state(len(soup.select("h1")) == 1),
        "single_lpv_header": state(len(soup.select("header.topbar")) == 1),
        "single_lpv_footer": state(len(soup.select("footer.lpv-site-footer")) == 1),
        "single_header_total": state(len(soup.select("header")) == 1),
        "single_footer_total": state(len(soup.select("footer")) == 1),
        "no_native_header": state(not soup.select("header.wp-block-template-part, .wp-block-template-part header")),
        "no_native_footer": state(not soup.select("footer.wp-block-template-part, .wp-block-template-part footer")),
        "no_native_post_title": state(not soup.select(".wp-block-post-title")),
        "no_native_featured_image": state(not soup.select(".wp-block-post-featured-image")),
        "lang": state(bool(soup.html) and soup.html.get("lang") == row["lang"]),
    }
    canonicals = [node.get("href") for node in soup.select('head link[rel="canonical"]')]
    checks["canonical_unique_self"] = state(canonicals == [row["canonical"]])
    titles = soup.select("head title")
    checks["title_unique_exact"] = state(len(titles) == 1 and titles[0].get_text() == metadata["title"])
    descriptions = soup.select('head meta[name="description" i]')
    checks["description_unique_exact"] = state(
        len(descriptions) == 1 and descriptions[0].get("content") == metadata["description"])
    alternates = [(node.get("hreflang"), node.get("href"))
                  for node in soup.select('head link[rel="alternate"][hreflang]')]
    checks["hreflang_exact_reciprocal_group"] = state(
        len(alternates) == len(row["alternates"]) and dict(alternates) == row["alternates"])
    checks["hreflang_self"] = state((row["lang"], row["canonical"]) in alternates)
    checks["x_default_pt"] = state(dict(alternates).get("x-default") == row["alternates"]["pt-BR"])
    if row["family"] == "lp_experiences":
        checks["lp_pt_xdefault_only"] = state(set(dict(alternates)) == {"pt-BR", "x-default"})
    privacy = soup.select('footer.lpv-site-footer a[href="/politica-de-privacidade/"]')
    checks["privacy_link"] = state(len(privacy) == 1 and privacy[0].get("hreflang") == "pt-BR")
    containers = soup.select(".wp-block-post-content")
    approved = (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_text(encoding="utf-8")
    stored = None
    if stored_page is not None and stored_page.get("exists"):
        stored = compare_stored_content(approved, stored_page.get("content", ""))
    checks["stored_content_preserved"] = (
        state(stored["content_preserved"]) if stored is not None else "NAO TESTADO")
    checks["stored_image_urls_preserved"] = (
        state(stored["image_urls_preserved"]) if stored is not None else "NAO TESTADO")

    rendered_content = {"preserved": False, "failures": ["content_container"],
                        "expected": {}, "observed": {}, "diagnostics": {}}
    rendered_images = {"primary_preserved": False, "derived_valid": False,
                       "failures": ["content_container"], "expected_primary_count": 0,
                       "observed_primary_count": 0, "primary_http_urls": [],
                       "derived_http_urls": [], "probe_targets": []}
    if len(containers) == 1:
        rendered_content = compare_rendered_content(approved, containers[0])
        rendered_images = compare_rendered_images(approved, containers[0])
    checks["rendered_content_preserved"] = state(rendered_content["preserved"])
    checks["rendered_primary_image_urls_preserved"] = state(rendered_images["primary_preserved"])
    probe_results = []
    if image_probe:
        targets = rendered_images.get("probe_targets", [])
        if not targets:
            targets = [{"url": url, "classification": "other", "source": "legacy",
                        "in_stored_content": False}
                       for url in rendered_images["primary_http_urls"]
                       + rendered_images["derived_http_urls"]]
        for target in targets:
            result = normalized_probe_result(target["url"], image_probe(target["url"]))
            probe_results.append({"page_id": row["id"], **target, **result})
    reachable = all(result["reachable"] for result in probe_results)
    checks["derived_image_urls_valid"] = state(rendered_images["derived_valid"] and reachable)
    body = response.get("body", "").lower()
    checks["aioseo_present"] = state("all in one seo" in body or "aioseo" in body)
    checks["yoast_absent"] = state("yoast" not in body)
    return {"id": row["id"], "path": row["url"], "http_status": response.get("status"),
            "final_url": response.get("url"), "checks": checks,
            "counts": {"main": len(soup.select("main")), "h1": len(soup.select("h1")),
                       "headers": len(soup.select("header")), "footers": len(soup.select("footer")),
                       "alternates": len(alternates)},
            "fidelity": {
                "rendered_content_failures": rendered_content["failures"],
                "rendered_content_expected": rendered_content["expected"],
                "rendered_content_observed": rendered_content["observed"],
                "rendered_content_diagnostics": rendered_content.get("diagnostics", {}),
                "rendered_image_failures": rendered_images["failures"],
                "expected_primary_images": rendered_images["expected_primary_count"],
                "observed_primary_images": rendered_images["observed_primary_count"],
                "image_probe_count": len(probe_results),
                "failed_image_probe_count": sum(not result["reachable"] for result in probe_results),
                "failed_image_probes": [result for result in probe_results if not result["reachable"]],
            }}


def inspect_non_lpv(response, expected_status=200):
    soup = BeautifulSoup(response.get("body", ""), "html.parser")
    return {"http": state(response.get("status") == expected_status),
            "no_lpv_header": state(not soup.select("header.topbar")),
            "no_lpv_footer": state(not soup.select("footer.lpv-site-footer")),
            "no_lpv_experiences_wrapper": state(not soup.select(".lp-experiences-page"))}


def audit(reader, stored_pages=None):
    rows = json.loads((PACKAGE / "language-map.json").read_bytes())["pages"]
    metadata = {row["id"]: row for row in json.loads((PACKAGE / "aioseo-metadata.json").read_bytes())}
    pages = [inspect_page(
        row, metadata[row["id"]], reader.get(row["url"]),
        (stored_pages or {}).get(str(row["id"])), getattr(reader, "probe_image", None),
    ) for row in rows]
    privacy_response = reader.get("/politica-de-privacidade/")
    privacy_soup = BeautifulSoup(privacy_response.get("body", ""), "html.parser")
    privacy = {"http_200": state(privacy_response.get("status") == 200),
               "expected_url": state(privacy_response.get("url") == ORIGIN + "/politica-de-privacidade/"),
               "has_document": state(bool(privacy_soup.html) and bool(privacy_soup.select("main"))),
               "no_lpv_template": state(not privacy_soup.select("header.topbar, footer.lpv-site-footer, .lp-experiences-page"))}
    nonce = "lpv-audit-7f1c9b"
    search_path = "/?" + urlencode({"s": nonce})
    search = inspect_non_lpv(reader.get(search_path), 200)
    not_found = inspect_non_lpv(reader.get("/" + nonce + "/"), 404)
    posts_result = reader.get("/wp-json/wp/v2/posts?per_page=1&_fields=link")
    post = {"status": "NAO TESTADO", "reason": "No public post discovered"}
    if posts_result.get("status") == 200:
        try:
            records = json.loads(posts_result.get("body", ""))
            if records and records[0].get("link", "").startswith(ORIGIN + "/"):
                path = records[0]["link"][len(ORIGIN):]
                post = inspect_non_lpv(reader.get(path), 200)
        except (json.JSONDecodeError, TypeError, KeyError):
            post = {"status": "NAO TESTADO", "reason": "REST post discovery was not valid JSON"}
    blockers = []
    for page in pages:
        blockers.extend(f"page:{page['id']}:{key}" for key, value in page["checks"].items() if value == "BLOQUEADOR")
    blockers.extend(f"privacy:{key}" for key, value in privacy.items() if value == "BLOQUEADOR")
    blockers.extend(f"search:{key}" for key, value in search.items() if value == "BLOQUEADOR")
    blockers.extend(f"404:{key}" for key, value in not_found.items() if value == "BLOQUEADOR")
    if isinstance(post, dict) and post.get("status") != "NAO TESTADO":
        blockers.extend(f"post:{key}" for key, value in post.items() if value == "BLOQUEADOR")
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "origin": ORIGIN, "method": "Unauthenticated public GET only; redirects disabled; no JS/forms/login",
            "pages": pages, "privacy": privacy, "search": search, "not_found": not_found, "sample_post": post,
            "blockers": blockers, "status": "APROVADO" if not blockers else "BLOQUEADOR",
            "forms_sent": 0, "ga_debugview": "NAO TESTADO", "zoom_200": "NAO TESTADO"}


def classify_baseline(strict_report):
    """Separate current operational safety from expected pre-deploy target differences."""
    report = copy.deepcopy(strict_report)
    strict_blockers = list(strict_report.get("blockers", []))
    operational_blockers = []
    target_differences = []

    for page in report.get("pages", []):
        for key, value in page.get("checks", {}).items():
            if value != "BLOQUEADOR":
                continue
            finding = f"page:{page['id']}:{key}"
            if key in BASELINE_OPERATIONAL_PAGE_CHECKS:
                operational_blockers.append(finding)
            else:
                page["checks"][key] = "EXPECTED_CHANGE"
                target_differences.append(finding)

    for section_name in ("privacy", "search", "not_found", "sample_post"):
        section = report.get(section_name, {})
        if section_name == "sample_post" and section.get("status") == "NAO TESTADO":
            continue
        prefix = "404" if section_name == "not_found" else (
            "post" if section_name == "sample_post" else section_name)
        for key, value in section.items():
            if value == "BLOQUEADOR":
                operational_blockers.append(f"{prefix}:{key}")

    classified = set(operational_blockers) | set(target_differences)
    operational_blockers.extend(item for item in strict_blockers if item not in classified)
    report["mode"] = "pre-deploy baseline"
    report["post_deploy_acceptance"] = {
        "status": strict_report.get("status"),
        "blocker_count": len(strict_blockers),
        "blockers": strict_blockers,
    }
    report["baseline_operational_safety"] = {
        "status": "APROVADO" if not operational_blockers else "BLOQUEADOR",
        "blocker_count": len(operational_blockers),
        "blockers": operational_blockers,
    }
    report["baseline_target_differences"] = {
        "status": "EXPECTED_CHANGE" if target_differences else "NO_CHANGE",
        "difference_count": len(target_differences),
        "differences": target_differences,
    }
    report["blockers"] = operational_blockers
    report["status"] = "APROVADO" if not operational_blockers else "BLOQUEADOR"
    return report


def baseline_audit(reader):
    return classify_baseline(audit(reader))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("baseline", "post-deploy"), default="post-deploy")
    args = parser.parse_args()
    if not args.confirm_production:
        parser.error("Refusing official production domain without --confirm-production.")
    report = (baseline_audit(ProductionReader()) if args.mode == "baseline"
              else audit(ProductionReader()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Production {args.mode} GET audit: {report['status']}; "
          f"{len(report['blockers'])} blockers. Report written.")
    return 2 if report["status"] == "BLOQUEADOR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
