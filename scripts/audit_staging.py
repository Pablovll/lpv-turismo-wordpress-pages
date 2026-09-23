#!/usr/bin/env python3
"""Explicit staging GET audit. No production, redirects, JS, forms or subresource crawling."""
import argparse
import base64
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from bs4 import BeautifulSoup

if __package__:
    from .preflight_staging import package_preflight
else:
    from preflight_staging import package_preflight

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "publication/stage-6"
MAX_BYTES = 5 * 1024 * 1024


def staging_origin(value):
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (not host or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or host in {"lpvturismo.com", "www.lpvturismo.com"}
            or parsed.scheme not in {"https", "http"}
            or (parsed.scheme == "http" and host not in {"127.0.0.1", "localhost", "::1"})
            or any(char.isspace() for char in value) or "\\" in value):
        raise ValueError("Use an explicit HTTPS staging origin, never production, credentials or a subdirectory.")
    parsed.port  # Validate malformed ports before constructing requests.
    return value.rstrip("/")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StagingReader:
    def __init__(self, base_url, username=None, password=None):
        self.origin = staging_origin(base_url)
        self.opener = build_opener(ProxyHandler({}), NoRedirects())
        if bool(username) != bool(password):
            raise ValueError("Both HTTP Basic environment variables are required, or neither.")
        if username and not self.origin.startswith("https://"):
            raise ValueError("HTTP Basic credentials require HTTPS.")
        self.authorization = None
        if username:
            self.authorization = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()

    def get(self, path):
        parsed = urlsplit(path)
        if (not path.startswith("/") or path.startswith("//") or parsed.netloc or parsed.scheme
                or parsed.query or parsed.fragment or "\\" in path or "%" in path
                or any(segment in {".", ".."} for segment in path.split("/"))):
            raise ValueError("Only root-relative paths without query or fragment are allowed.")
        headers = {"User-Agent": "LPV-Staging-ReadOnly-Audit/1.0", "Accept": "text/html,text/css"}
        if self.authorization:
            headers["Authorization"] = self.authorization
        request = Request(self.origin + path, headers=headers, method="GET")
        try:
            try:
                response = self.opener.open(request, timeout=25)
            except HTTPError as error:
                response = error
            with response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    return {"status": 0, "error": "response_size_limit"}
                return {"status": response.status, "url": response.url, "body": body.decode("utf-8"),
                        "headers": dict(response.headers.items())}
        except (URLError, TimeoutError, OSError, UnicodeError):
            return {"status": 0, "error": "request_failed_no_sensitive_details_logged"}


def check(condition):
    return "APROVADO" if condition else "BLOQUEADOR"


def normalize(value):
    return value.replace("\r\n", "\n").strip()


def fragment_features(soup):
    """Hashes/counters for approved content, without retaining form values in reports."""
    features = Counter()
    for node in soup.find_all(True):
        features[("tag", node.name)] += 1
        for key, value in node.attrs.items():
            if key == "class":
                for token in value:
                    features[(node.name, key, token)] += 1
            else:
                features[(node.name, key, json.dumps(value, sort_keys=True))] += 1
    scripts = [hashlib.sha256(normalize(node.get_text()).encode()).hexdigest() for node in soup.select("script")]
    text = " ".join(soup.get_text(" ", strip=True).split())
    return features, scripts, text


def inspect_page(row, metadata, response, origin, canonical_mode, hreflang_mode):
    soup = BeautifulSoup(response.get("body", ""), "html.parser")
    checks = {"http_200": check(response["status"] == 200),
              "expected_url_no_redirect": check(response.get("url") == origin + row["url"]),
              "html_document": check(len(soup.select("html")) == len(soup.select("head")) == len(soup.select("body")) == 1)}
    for selector in ("main", "h1", "header", "footer", "header.topbar", "footer.lpv-site-footer"):
        checks[selector] = check(len(soup.select(selector)) == 1)
    for selector in (".wp-block-template-part", ".wp-block-post-title", ".wp-block-post-featured-image"):
        checks["absent:" + selector] = check(not soup.select(selector))
    checks["lang"] = check(bool(soup.html) and soup.html.get("lang") == row["lang"])
    expected_canonical = row["canonical"] if canonical_mode == "approved" else origin + row["url"]
    canonical = [node.get("href") for node in soup.select('link[rel="canonical"]')]
    checks["canonical_unique_expected"] = check(canonical == [expected_canonical] and bool(soup.head)
                                               and len(soup.head.select('link[rel="canonical"]')) == 1)
    titles = soup.select("title")
    checks["title"] = check(len(titles) == 1 and bool(soup.head) and len(soup.head.select("title")) == 1
                            and titles[0].get_text() == metadata["title"])
    descriptions = soup.select('meta[name="description" i]')
    checks["description"] = check(len(descriptions) == 1 and bool(soup.head)
                                  and len(soup.head.select('meta[name="description" i]')) == 1
                                  and descriptions[0].get("content") == metadata["description"])
    link_header = next((value for key, value in response.get("headers", {}).items() if key.lower() == "link"), "").lower()
    checks["no_unreviewed_http_link_seo"] = check("canonical" not in link_header and "hreflang" not in link_header)
    privacy_links = soup.select('footer.lpv-site-footer a[href="/politica-de-privacidade/"]')
    checks["privacy_link"] = check(len(privacy_links) == 1 and privacy_links[0].get("hreflang") == "pt-BR")
    alternates = [(node.get("hreflang"), node.get("href")) for node in soup.select('link[rel="alternate"][hreflang]')]
    if hreflang_mode == "suppressed":
        checks["hreflang_safety_suppression"] = check(not alternates)
        checks["published_reciprocity"] = "NAO TESTADO"
    else:
        checks["hreflang_exact_group_self_xdefault"] = check(
            len(alternates) == len(row["alternates"]) and dict(alternates) == row["alternates"]
            and bool(soup.head) and len(soup.head.select('link[rel="alternate"][hreflang]')) == len(alternates))
    containers = soup.select(".wp-block-post-content")
    fidelity = False
    if len(containers) == 1:
        original = BeautifulSoup((PACKAGE / "html" / row["source"].removeprefix("pages/")).read_bytes(), "html.parser")
        expected, scripts, text = fragment_features(original)
        actual, actual_scripts, actual_text = fragment_features(containers[0])
        fidelity = expected == actual and scripts == actual_scripts and text == actual_text
    checks["approved_fragment_features_scripts_text"] = check(fidelity)
    css = normalize((PACKAGE / "css/lpv-style.css").read_text(encoding="utf-8"))
    checks["approved_inline_css"] = "APROVADO" if any(normalize(node.get_text()) == css for node in soup.select("style")) else "NAO TESTADO"
    checks.update({key: "NAO TESTADO" for key in ("image_loading_and_scale", "horizontal_overflow",
                   "computed_css_cascade", "aioseo_og_twitter_schema_robots_sitemap", "cache_renewal", "wp_publish_status")})
    return {"id": row["id"], "path": row["url"], "http_status": response["status"], "checks": checks}


def audit(reader, canonical_mode="staging", hreflang_mode="suppressed", css_path=None):
    rows = json.loads((PACKAGE / "language-map.json").read_bytes())["pages"]
    metadata = {row["id"]: row for row in json.loads((PACKAGE / "aioseo-metadata.json").read_bytes())}
    pages = [inspect_page(row, metadata[row["id"]], reader.get(row["url"]), reader.origin,
                          canonical_mode, hreflang_mode) for row in rows]
    privacy_path = "/politica-de-privacidade/"
    privacy = reader.get(privacy_path)
    privacy_soup = BeautifulSoup(privacy.get("body", ""), "html.parser")
    legal = {"http_200": check(privacy["status"] == 200),
             "expected_url": check(privacy.get("url") == reader.origin + privacy_path),
             "content_legal_review": "NAO TESTADO",
             "has_document_and_main": check(bool(privacy_soup.html) and bool(privacy_soup.select("main")))}
    css_result = "NAO TESTADO"
    if css_path:
        if not css_path.startswith("/wp-content/") or not css_path.endswith(".css"):
            raise ValueError("CSS path must be a known /wp-content/ file ending in .css.")
        result = reader.get(css_path)
        css_result = check(result["status"] == 200 and normalize(result.get("body", ""))
                           == normalize((PACKAGE / "css/lpv-style.css").read_text(encoding="utf-8")))
    blocked = css_result == "BLOQUEADOR" or "BLOQUEADOR" in legal.values() or any(
        "BLOQUEADOR" in page["checks"].values() for page in pages)
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "origin": reader.origin,
            "method": "GET only, no redirects, no subresources, no JS or submission",
            "canonical_mode": canonical_mode, "hreflang_mode": hreflang_mode,
            "status": "BLOQUEADOR" if blocked else "PENDENTE", "staging_approved": False,
            "pages": pages, "privacy": legal, "approved_external_css": css_result,
            "manual_acceptance": "PENDENTE", "forms_sent": 0, "ga_events_triggered": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--canonical-mode", choices=("staging", "approved"), default="staging")
    parser.add_argument("--hreflang-mode", choices=("suppressed", "published"), default="suppressed")
    parser.add_argument("--css-path")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        reader = StagingReader(args.base_url, os.getenv("LPV_STAGING_HTTP_USER"), os.getenv("LPV_STAGING_HTTP_PASSWORD"))
        if package_preflight()["status"] != "APROVADO":
            raise ValueError("Stage 6 package integrity failed; no requests made.")
        if args.css_path and (not args.css_path.startswith("/wp-content/") or not args.css_path.endswith(".css")
                              or urlsplit(args.css_path).query or urlsplit(args.css_path).fragment):
            raise ValueError("Invalid known CSS path.")
        report = audit(reader, args.canonical_mode, args.hreflang_mode, args.css_path)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"GET checks: {report['status']}. Staging acceptance remains manual. Report written.")
    return 2 if report["status"] == "BLOQUEADOR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
