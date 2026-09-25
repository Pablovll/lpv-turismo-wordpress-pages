#!/usr/bin/env python3
"""Semantic content and image fidelity contracts for LPV WordPress pages."""
import base64
import binascii
import hashlib
import html
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment, Declaration, Doctype, ProcessingInstruction


ESSENTIAL_CLASS_NAMES = {
    "topbar", "container", "hero", "cards", "lpv-service-card",
    "lpv-simple-page", "lpv-page-hero", "lpv-content-section",
    "process", "cta", "footer",
}
SKIPPED_TEXT_PARENTS = {"script", "style", "template", "noscript"}
SKIPPED_TEXT_NODES = (Comment, Declaration, Doctype, ProcessingInstruction)
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
CSS_IMAGE_EXTENSIONS = (".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp")


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
        if (not isinstance(node, SKIPPED_TEXT_NODES)
                and node.parent and node.parent.name not in SKIPPED_TEXT_PARENTS):
            values.append(str(node))
    return normalize_text(" ".join(values))


def code_tokens(value):
    return tuple(token for token in CODE_TOKEN.findall(value)
                 if not token.startswith("//") and not token.startswith("/*"))


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def text_diagnostics(expected, observed):
    expected_tokens = expected.split()
    observed_tokens = observed.split()
    matcher = SequenceMatcher(a=expected_tokens, b=observed_tokens, autojunk=False)
    opcode = next((item for item in matcher.get_opcodes() if item[0] != "equal"),
                  ("equal", len(expected_tokens), len(expected_tokens),
                   len(observed_tokens), len(observed_tokens)))
    kind, expected_start, expected_end, observed_start, observed_end = opcode
    character_index = next(
        (index for index, pair in enumerate(zip(expected, observed)) if pair[0] != pair[1]),
        min(len(expected), len(observed)),
    )
    approved_tokens = set(expected_tokens)

    def safe_observed(token):
        if token not in approved_tokens:
            return "[REDACTED]"
        if "@" in token or re.search(r"\d{6,}", token):
            return "[REDACTED]"
        return token

    expected_context = expected_tokens[max(0, expected_start - 4):min(
        len(expected_tokens), max(expected_end, expected_start + 1) + 4)]
    observed_context = observed_tokens[max(0, observed_start - 4):min(
        len(observed_tokens), max(observed_end, observed_start + 1) + 4)]
    snippets = []
    if expected_context:
        snippets.append({"kind": "expected_approved", "text": " ".join(expected_context)})
    if observed_context:
        snippets.append({"kind": "observed_redacted",
                         "text": " ".join(safe_observed(token) for token in observed_context)})
    return {
        "expected_sha256": sha256_text(expected),
        "observed_sha256": sha256_text(observed),
        "expected_length": len(expected),
        "observed_length": len(observed),
        "expected_token_count": len(expected_tokens),
        "observed_token_count": len(observed_tokens),
        "first_divergence": {
            "character_index": character_index,
            "token_index": min(expected_start, observed_start),
            "type": {"delete": "removed", "insert": "added", "replace": "replaced"}.get(kind, kind),
        },
        "safe_snippets": snippets[:3],
    }


CLASSIC_SCRIPT_TYPES = {
    "", "text/javascript", "application/javascript", "text/ecmascript",
    "application/ecmascript", "litespeed/javascript",
}
SCRIPT_RELEVANT_ATTRIBUTES = (
    "async", "defer", "nomodule", "integrity", "crossorigin", "referrerpolicy",
)


def canonical_script_type(node):
    value = node.get("type", "").strip().lower()
    return "classic" if value in CLASSIC_SCRIPT_TYPES else value


def canonical_script_src(node):
    source = node.get("src", "")
    if not source and node.get("type", "").strip().lower() == "litespeed/javascript":
        source = node.get("data-src") or node.get("data-lazy-src") or ""
    return html.unescape(source)


def script_relevant_attributes(node):
    values = []
    for name in SCRIPT_RELEVANT_ATTRIBUTES:
        if name in {"async", "defer", "nomodule"}:
            values.append((name, node.has_attr(name)))
        else:
            values.append((name, html.unescape(node.get(name, ""))))
    return tuple(values)


def script_signature(node):
    return (canonical_script_src(node), canonical_script_type(node),
            script_relevant_attributes(node), code_tokens(node.get_text()))


def script_record(node, index):
    if node is None:
        return {"index": index, "presence": False}
    tokens = code_tokens(node.get_text())
    source = canonical_script_src(node)
    parsed_source = urlsplit(source)
    report_source = source
    if parsed_source.scheme and parsed_source.netloc:
        report_source = urlunsplit((parsed_source.scheme, parsed_source.hostname or "",
                                    parsed_source.path, "", ""))
    return {
        "index": index,
        "presence": True,
        "type": node.get("type", ""),
        "canonical_type": canonical_script_type(node),
        "src": report_source,
        "inline_length": len(node.get_text()),
        "normalized_sha256": sha256_text("\x1f".join(tokens)),
        "token_count": len(tokens),
        "relevant_attributes": dict(script_relevant_attributes(node)),
    }


def script_diagnostics(expected_soup, observed_soup):
    expected_nodes = expected_soup.select("script")
    observed_nodes = observed_soup.select("script")
    records = []
    for index in range(max(len(expected_nodes), len(observed_nodes))):
        expected = expected_nodes[index] if index < len(expected_nodes) else None
        observed = observed_nodes[index] if index < len(observed_nodes) else None
        expected_signature = script_signature(expected) if expected is not None else None
        observed_signature = script_signature(observed) if observed is not None else None
        differences = []
        if expected is None or observed is None:
            differences.append("presence")
        else:
            for name, left, right in zip(
                    ("src", "type", "attributes", "code"),
                    expected_signature, observed_signature):
                if left != right:
                    differences.append(name)
        records.append({
            "index": index,
            "equivalent": expected_signature == observed_signature,
            "differences": differences,
            "expected": script_record(expected, index),
            "observed": script_record(observed, index),
        })
    return records


def css_tokens(value):
    def quoted_url(match):
        url = match.group(2).strip().replace("\\", "\\\\").replace('"', '\\"')
        return 'url("' + url + '")'

    value = CSS_URL.sub(quoted_url, value)
    value = re.sub(r";\s*}", "}", value)
    return code_tokens(value)


def is_css_image_url(value):
    parsed = urlsplit(value)
    path = unquote(parsed.path).lower()
    return path.endswith(CSS_IMAGE_EXTENSIONS)


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
        "scripts": tuple(script_signature(node) for node in soup.select("script")),
        "styles": tuple(css_tokens(node.get_text()) for node in soup.select("style")),
    }


def compare_rendered_content(approved, rendered):
    expected_soup = parse_fragment(approved)
    actual_soup = parse_fragment(rendered)
    expected = content_manifest(expected_soup)
    actual = content_manifest(actual_soup)
    failures = []
    for key in ("text", "headings", "links", "buttons", "ids", "structure",
                "forms", "scripts", "styles"):
        if expected[key] != actual[key]:
            failures.append(key)
    if expected["classes"] - actual["classes"]:
        failures.append("essential_classes")
    if expected["attributes"] - actual["attributes"]:
        failures.append("aria_or_data_attributes")
    diagnostics = {}
    if "text" in failures:
        diagnostics["text"] = text_diagnostics(expected["text"], actual["text"])
    if "scripts" in failures:
        diagnostics["scripts"] = script_diagnostics(expected_soup, actual_soup)
    return {
        "preserved": not failures,
        "failures": failures,
        "diagnostics": diagnostics,
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
    return [html.unescape(value) for value in values
            if value and not value.lower().startswith("data:") and is_css_image_url(value)]


def css_url_entries(soup):
    entries = []
    for index, node in enumerate(soup.select("[style]")):
        for match in CSS_URL.findall(node.get("style", "")):
            value = html.unescape(match[1].strip())
            if (value and not value.lower().startswith("data:")
                    and is_css_image_url(value)):
                entries.append((value, f"{node.name}[style]:{index}"))
    for index, node in enumerate(soup.select("style")):
        for match in CSS_URL.findall(node.get_text()):
            value = html.unescape(match[1].strip())
            if (value and not value.lower().startswith("data:")
                    and is_css_image_url(value)):
                entries.append((value, f"style:{index}"))
    return entries


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
    probe_targets = []
    rendered_soup = parse_fragment(rendered)
    expected_nodes = parse_fragment(approved).select("img, source")
    actual_nodes = rendered_soup.select("img, source")
    if len(expected_nodes) != len(actual_nodes):
        failures.append("image_element_count")
    for index, node in enumerate(actual_nodes):
        source = html.unescape(node.get("src", ""))
        logical_source = source
        source_attribute = "src"
        if source.lower().startswith("data:") and not safe_svg_placeholder(source):
            failures.append(f"unsafe_placeholder:{index}")
        if source.lower().startswith("data:"):
            logical_source = html.unescape(node.get("data-src") or node.get("data-lazy-src") or "")
            source_attribute = "data-src" if node.get("data-src") else "data-lazy-src"
        if logical_source.startswith(("http://", "https://")):
            probe_targets.append({
                "url": logical_source,
                "classification": "LiteSpeed" if source_attribute != "src" else "primary",
                "source": f"{node.name}[{index}].{source_attribute}",
                "in_stored_content": logical_source in approved_urls,
            })
        for attribute in ("srcset", "data-srcset", "data-lazy-srcset"):
            for candidate in parse_srcset(node.get(attribute, "")):
                derived_http_urls.append(candidate)
                probe_targets.append({
                    "url": candidate,
                    "classification": "LiteSpeed" if attribute != "srcset" else "srcset",
                    "source": f"{node.name}[{index}].{attribute}",
                    "in_stored_content": candidate in approved_urls,
                })
                if not valid_derived_url(candidate, approved_urls):
                    failures.append(f"invalid_derived_url:{index}:{attribute}")
    for value, source in css_url_entries(rendered_soup):
        if value.startswith(("http://", "https://")):
            probe_targets.append({
                "url": value, "classification": "CSS", "source": source,
                "in_stored_content": value in approved_urls,
            })
    unique_targets = []
    seen_targets = set()
    for target in probe_targets:
        if target["url"] not in seen_targets:
            unique_targets.append(target)
            seen_targets.add(target["url"])
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
        "probe_targets": unique_targets,
    }
