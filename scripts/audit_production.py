#!/usr/bin/env python3
"""Read-only LPV production audit. Requires an explicit production gate."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from bs4 import BeautifulSoup

if __package__:
    from .audit_staging import fragment_features
else:
    from audit_staging import fragment_features

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "publication/stage-6"
ORIGIN = "https://lpvturismo.com"
MAX_BYTES = 5 * 1024 * 1024


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ProductionReader:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

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


def state(condition):
    return "APROVADO" if condition else "BLOQUEADOR"


def image_urls(soup):
    urls = set()
    for image in soup.select("img[src], source[src]"):
        for attribute in ("src",):
            if image.get(attribute):
                for candidate in image[attribute].split(","):
                    value = candidate.strip().split(" ", 1)[0]
                    if value:
                        urls.add(value)
    for node in soup.select("[style]"):
        style = node.get("style", "")
        start = 0
        while True:
            start = style.find("url(", start)
            if start < 0:
                break
            end = style.find(")", start + 4)
            if end < 0:
                break
            urls.add(style[start + 4:end].strip(" \"'"))
            start = end + 1
    return sorted(urls)


def inspect_page(row, metadata, response):
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
    expected_soup = BeautifulSoup(
        (PACKAGE / "html" / row["source"].removeprefix("pages/")).read_bytes(), "html.parser")
    fidelity = False
    if len(containers) == 1:
        expected_features, expected_scripts, expected_text = fragment_features(expected_soup)
        actual_features, actual_scripts, actual_text = fragment_features(containers[0])
        fidelity = (expected_features == actual_features and expected_scripts == actual_scripts
                    and expected_text == actual_text)
    checks["approved_content_preserved"] = state(fidelity)
    expected_images = image_urls(expected_soup)
    actual_images = image_urls(containers[0]) if len(containers) == 1 else []
    checks["image_urls_preserved"] = state(expected_images == actual_images)
    body = response.get("body", "").lower()
    checks["aioseo_present"] = state("all in one seo" in body or "aioseo" in body)
    checks["yoast_absent"] = state("yoast" not in body)
    return {"id": row["id"], "path": row["url"], "http_status": response.get("status"),
            "final_url": response.get("url"), "checks": checks,
            "counts": {"main": len(soup.select("main")), "h1": len(soup.select("h1")),
                       "headers": len(soup.select("header")), "footers": len(soup.select("footer")),
                       "alternates": len(alternates)},
            "image_url_count": len(actual_images)}


def inspect_non_lpv(response, expected_status=200):
    soup = BeautifulSoup(response.get("body", ""), "html.parser")
    return {"http": state(response.get("status") == expected_status),
            "no_lpv_header": state(not soup.select("header.topbar")),
            "no_lpv_footer": state(not soup.select("footer.lpv-site-footer")),
            "no_lpv_experiences_wrapper": state(not soup.select(".lp-experiences-page"))}


def audit(reader):
    rows = json.loads((PACKAGE / "language-map.json").read_bytes())["pages"]
    metadata = {row["id"]: row for row in json.loads((PACKAGE / "aioseo-metadata.json").read_bytes())}
    pages = [inspect_page(row, metadata[row["id"]], reader.get(row["url"])) for row in rows]
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.confirm_production:
        parser.error("Refusing official production domain without --confirm-production.")
    report = audit(ProductionReader())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Production GET audit: {report['status']}; {len(report['blockers'])} blockers. Report written.")
    return 2 if report["status"] == "BLOQUEADOR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
