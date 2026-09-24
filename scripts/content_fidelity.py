#!/usr/bin/env python3
"""Semantic content and image fidelity contracts for LPV WordPress pages."""
import base64
import binascii
import html
import re
import unicodedata
from collections import Counter
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


ESSENTIAL_CLASS_NAMES = {
    "topbar", "container", "hero", "cards", "lpv-service-card",
    "lpv-simple-page", "lpv-page-hero", "lpv-content-section",
    "process", "cta", "footer",
}
SKIPPED_TEXT_PARENTS = {"script", "style", "template", "noscript"}
TYPOGRAPHY_EQUIVALENTS = str.maketrans({
    "\u00a0": " ", "\u2018": "'", "\u2019": "'", "\u201a": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...",
})
CODE_TOKEN = re.compile(
    r"//[^\r\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|"
    r"===|!==|=>|==|!=|<=|>=|\+\+|--|&&|\|\||\?\?|\.\.\.|[^\s]",
    re.DOTALL,
)
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)


def parse_fragment(value):
    if isinstance(value, BeautifulSoup) or getattr(value, "name", None):
        return value
    return BeautifulSoup(value, "html.parser")


def normalize_text(value):
    value = html.unescape(str(value))
    value = unicodedata.normalize("NFC", value).translate(TYPOGRAPHY_EQUIVALENTS)
    return " ".join(value.split())


def visible_text(soup):
    values = []
    for node in soup.find_all(string=True):
        if node.parent and node.parent.name not in SKIPPED_TEXT_PARENTS:
            values.append(str(node))
    return normalize_text(" ".join(values))


def code_tokens(value):
    return tuple(token for token in CODE_TOKEN.findall(value)
                 if not token.startswith("//") and not token.startswith("/*"))


def css_tokens(value):
    value = CSS_URL.sub(lambda match: "url(" + match.group(2).strip() + ")", value)
    return code_tokens(value)


def essential_classes(node):
    return tuple(sorted(token for token in node.get("class", [])
                        if token in ESSENTIAL_CLASS_NAMES
                        or token.startswith("lpv-") or token.startswith("lp-")))


def required_class_counts(soup):
    counts = Counter()
    for node in soup.find_all(True):
        for token in essential_classes(node):
            counts[(node.name, token)] += 1
    return counts


def required_attribute_counts(soup):
    counts = Counter()
    for node in soup.find_all(True):
        for key, value in node.attrs.items():
            if key.startswith("aria-") or key.startswith("data-"):
                normalized = tuple(value) if isinstance(value, list) else str(value)
                counts[(node.name, key, normalized)] += 1
    return counts


def structure_signature(soup):
    signature = []
    for node in soup.select("header, nav, section, footer"):
        headings = tuple((heading.name, normalize_text(heading.get_text(" ", strip=True)))
                         for heading in node.select("h1, h2, h3"))
        signature.append((node.name, node.get("id", ""), essential_classes(node), headings))
    return tuple(signature)


def form_signature(soup):
    forms = []
    for form in soup.select("form"):
        fields = []
        for field in form.select("input, select, textarea, button"):
            item = {
                "tag": field.name,
                "name": field.get("name", ""),
                "type": field.get("type", ""),
                "required": field.has_attr("required"),
            }
            if field.name == "input" and field.get("type", "").lower() == "hidden":
                item["value"] = field.get("value", "")
            if field.name == "select":
                item["options"] = tuple(
                    (option.get("value", ""), normalize_text(option.get_text(" ", strip=True)),
                     option.has_attr("selected"))
                    for option in field.select("option")
                )
            fields.append(tuple(sorted(item.items())))
        labels = tuple((label.get("for", ""), normalize_text(label.get_text(" ", strip=True)))
                       for label in form.select("label"))
        forms.append((form.get("action", ""), form.get("method", "get").lower(),
                      tuple(fields), labels))
    return tuple(forms)


def content_manifest(value):
    soup = parse_fragment(value)
    return {
        "text": visible_text(soup),
        "headings": tuple((node.name, normalize_text(node.get_text(" ", strip=True)))
                          for node in soup.select("h1, h2, h3")),
        "links": tuple((node.name, normalize_text(node.get_text(" ", strip=True)),
                        html.unescape(node.get("href", "")))
                       for node in soup.select("a[href]")),
        "buttons": tuple((normalize_text(node.get_text(" ", strip=True)),
                          node.get("type", ""), node.get("name", ""), node.get("value", ""))
                         for node in soup.select("button")),
        "ids": Counter(node.get("id") for node in soup.select("[id]")),
        "classes": required_class_counts(soup),
        "attributes": required_attribute_counts(soup),
        "structure": structure_signature(soup),
        "forms": form_signature(soup),
        "scripts": tuple((node.get("src", ""), node.get("type", ""), code_tokens(node.get_text()))
                         for node in soup.select("script")),
        "styles": tuple(css_tokens(node.get_text()) for node in soup.select("style")),
    }


def compare_rendered_content(approved, rendered):
    expected = content_manifest(approved)
    actual = content_manifest(rendered)
    failures = []
    for key in ("text", "headings", "links", "buttons", "ids", "structure",
                "forms", "scripts", "styles"):
        if expected[key] != actual[key]:
            failures.append(key)
    if expected["classes"] - actual["classes"]:
        failures.append("essential_classes")
    if expected["attributes"] - actual["attributes"]:
        failures.append("aria_or_data_attributes")
    return {
        "preserved": not failures,
        "failures": failures,
        "expected": {
            "headings": len(expected["headings"]), "links": len(expected["links"]),
            "forms": len(expected["forms"]), "scripts": len(expected["scripts"]),
            "styles": len(expected["styles"]), "ids": sum(expected["ids"].values()),
        },
        "observed": {
            "headings": len(actual["headings"]), "links": len(actual["links"]),
            "forms": len(actual["forms"]), "scripts": len(actual["scripts"]),
            "styles": len(actual["styles"]), "ids": sum(actual["ids"].values()),
        },
    }


def css_urls(soup):
    values = []
    for node in soup.select("[style]"):
        values.extend(match[1].strip() for match in CSS_URL.findall(node.get("style", "")))
    for node in soup.select("style"):
        values.extend(match[1].strip() for match in CSS_URL.findall(node.get_text()))
    return [html.unescape(value) for value in values if value and not value.lower().startswith("data:")]


def editorial_image_entries(value, rendered=False):
    soup = parse_fragment(value)
    entries = []
    for node in soup.select("img, source"):
        source = html.unescape(node.get("src", ""))
        if rendered and source.lower().startswith("data:"):
            source = html.unescape(node.get("data-src") or node.get("data-lazy-src") or "")
        if source:
            entries.append((node.name, source, normalize_text(node.get("alt", ""))))
    return entries


def editorial_image_urls(value, rendered=False):
    soup = parse_fragment(value)
    return [entry[1] for entry in editorial_image_entries(soup, rendered=rendered)] + css_urls(soup)


def compare_stored_content(approved, stored):
    return {
        "content_preserved": approved == stored,
        "image_urls_preserved": editorial_image_urls(approved) == editorial_image_urls(stored),
    }


def parse_srcset(value):
    candidates = []
    for match in re.finditer(r"(?:^|,\s*)((?:https?://|/)[^\s,]+)(?:\s+[0-9.]+[wx])?", value or ""):
        candidates.append(html.unescape(match.group(1)))
    return candidates


def safe_svg_placeholder(value):
    prefix = "data:image/svg+xml;base64,"
    if not value.startswith(prefix):
        return False
    try:
        decoded = base64.b64decode(value[len(prefix):], validate=True)
    except (binascii.Error, ValueError):
        return False
    if not decoded or len(decoded) > 64 * 1024:
        return False
    lowered = decoded.lower()
    return (b"<svg" in lowered and b"<script" not in lowered and b"javascript:" not in lowered
            and not re.search(br"\son[a-z]+\s*=", lowered))


def image_family(url):
    parsed = urlsplit(url)
    name = unquote(PurePosixPath(parsed.path).name)
    stem = name
    for extension in (".webp", ".avif", ".jpg", ".jpeg", ".png", ".gif"):
        if stem.lower().endswith(extension):
            stem = stem[:-len(extension)]
    stem = re.sub(r"-\d+x\d+$", "", stem)
    stem = re.sub(r"-scaled$", "", stem)
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), str(PurePosixPath(parsed.path).parent), stem


def valid_derived_url(candidate, approved_urls):
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        return False
    if not parsed.hostname or not parsed.path.startswith("/wp-content/uploads/"):
        return False
    family = image_family(candidate)
    return any(family == image_family(approved) for approved in approved_urls
               if approved.startswith("https://"))


def compare_rendered_images(approved, rendered):
    expected = editorial_image_entries(approved)
    actual = editorial_image_entries(rendered, rendered=True)
    failures = []
    if expected != actual:
        failures.append("primary_images_or_alt")
    expected_css = css_urls(parse_fragment(approved))
    actual_css = css_urls(parse_fragment(rendered))
    if expected_css != actual_css:
        failures.append("css_image_urls")

    approved_urls = [entry[1] for entry in expected] + expected_css
    derived_http_urls = []
    rendered_soup = parse_fragment(rendered)
    expected_nodes = parse_fragment(approved).select("img, source")
    actual_nodes = rendered_soup.select("img, source")
    if len(expected_nodes) != len(actual_nodes):
        failures.append("image_element_count")
    for index, node in enumerate(actual_nodes):
        source = html.unescape(node.get("src", ""))
        if source.lower().startswith("data:") and not safe_svg_placeholder(source):
            failures.append(f"unsafe_placeholder:{index}")
        for attribute in ("srcset", "data-srcset", "data-lazy-srcset"):
            for candidate in parse_srcset(node.get(attribute, "")):
                derived_http_urls.append(candidate)
                if not valid_derived_url(candidate, approved_urls):
                    failures.append(f"invalid_derived_url:{index}:{attribute}")
    return {
        "primary_preserved": expected == actual and expected_css == actual_css,
        "derived_valid": not any(item.startswith(("unsafe_placeholder", "invalid_derived_url"))
                                 or item == "image_element_count" for item in failures),
        "failures": sorted(set(failures)),
        "expected_primary_count": len(expected) + len(expected_css),
        "observed_primary_count": len(actual) + len(actual_css),
        "primary_http_urls": sorted(set(
            [entry[1] for entry in actual if entry[1].startswith("https://")]
            + [url for url in actual_css if url.startswith("https://")]
        )),
        "derived_http_urls": sorted(set(derived_http_urls)),
    }
