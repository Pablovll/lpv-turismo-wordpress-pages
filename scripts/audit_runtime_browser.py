#!/usr/bin/env python3
"""Side-effect-free Chromium acceptance for the optimized LPV frontend."""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

if __package__:
    from .production_common import ORIGIN, PACKAGE, dump_json, load_pages
else:
    from production_common import ORIGIN, PACKAGE, dump_json, load_pages

BLOCKED_HOST_SUFFIXES = (
    "formsubmit.co", "google-analytics.com", "analytics.google.com",
    "googletagmanager.com", "wa.me", "whatsapp.com",
)
FORM_PAGE_IDS = {19: "Português", 203: "Español", 218: "English"}
PII_SENTINELS = ("LPV Runtime Test", "runtime@example.test", "+5500000000000")
BROWSER_LOG_SOURCES = {
    "other", "security", "rendering", "intervention", "deprecation",
    "recommendation", "violation",
}
CRITICAL_RESOURCE_TYPES = {"document", "script", "stylesheet", "image", "font"}


def browser_executable():
    candidates = [
        os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
    ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


def sanitized_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}{parsed.path}"


def same_origin(url, origin):
    if not url:
        return False
    parsed = urlsplit(url)
    expected = urlsplit(origin)
    return (parsed.scheme, parsed.hostname, parsed.port) == (
        expected.scheme, expected.hostname, expected.port)


def cdp_stack_urls(stack):
    urls = []
    while isinstance(stack, dict):
        urls.extend(frame.get("url", "") for frame in stack.get("callFrames", []))
        stack = stack.get("parent")
    return [sanitized_url(url) for url in urls if url]


def cdp_argument_text(arguments):
    values = []
    for argument in arguments or []:
        if "value" in argument:
            values.append(str(argument["value"]))
        elif argument.get("description"):
            values.append(str(argument["description"]))
    return " ".join(values)[:1000]


def classify_runtime_event(event, origin):
    item = {
        "message": str(event.get("message", ""))[:1000],
        "category": "THIRD_PARTY_DIAGNOSTIC",
        "channel": event.get("channel", "unknown"),
        "source": event.get("source", ""),
        "level": event.get("level", ""),
        "url": sanitized_url(event.get("url", "")) if event.get("url") else "",
        "line": event.get("line"),
        "column": event.get("column"),
        "stack_urls": [sanitized_url(url) for url in event.get("stack_urls", []) if url],
        "request_url": (sanitized_url(event.get("request_url", ""))
                        if event.get("request_url") else ""),
        "resource_type": event.get("resource_type", ""),
        "same_origin": False,
        "browser_internal": False,
        "blocker": False,
        "reason": "Third-party diagnostic without demonstrated LPV impact.",
    }
    evidence_urls = [item["url"], item["request_url"], *item["stack_urls"]]
    first_party = any(same_origin(url, origin) for url in evidence_urls if url)
    first_party_stack = any(same_origin(url, origin) for url in item["stack_urls"])
    item["same_origin"] = first_party
    channel = item["channel"]
    source = item["source"].lower()
    level = item["level"].lower()
    message = item["message"].lower()

    if (channel == "cdp_log" and source == "other" and not first_party_stack
            and "provider" in message and "accounts list is empty" in message):
        item.update({
            "category": "FEDCM_BROWSER_DIAGNOSTIC",
            "browser_internal": True,
            "reason": "Chromium/FedCM log entry with browser source and no first-party stack.",
        })
    elif channel == "cdp_log" and source in BROWSER_LOG_SOURCES and not first_party_stack:
        item.update({
            "category": "BROWSER_DIAGNOSTIC",
            "browser_internal": True,
            "reason": "Chromium log source without first-party script evidence.",
        })
    elif channel in {"playwright_pageerror", "cdp_exception"} and first_party:
        item.update({
            "category": "FIRST_PARTY_EXCEPTION", "blocker": True,
            "reason": "JavaScript exception has a same-origin script or stack URL.",
        })
    elif channel in {"playwright_console", "cdp_console"} and level == "error" and first_party:
        item.update({
            "category": "FIRST_PARTY_CONSOLE_ERROR", "blocker": True,
            "reason": "console.error has a same-origin location or stack URL.",
        })
    elif channel in {"playwright_request_failed", "playwright_response_failed",
                     "cdp_network_failed", "cdp_response_failed"}:
        if first_party and item["resource_type"] in CRITICAL_RESOURCE_TYPES:
            item.update({
                "category": "FIRST_PARTY_RESOURCE_FAILURE", "blocker": True,
                "reason": "Required first-party resource failed to load.",
            })
        else:
            item["reason"] = "Non-critical or third-party resource failure."
    elif first_party and level == "error":
        item.update({
            "category": "FIRST_PARTY_CONSOLE_ERROR", "blocker": True,
            "reason": "Same-origin error without browser-internal provenance.",
        })
    return item


def classify_runtime_events(events, origin):
    classified = [classify_runtime_event(event, origin) for event in events]
    browser_messages = {
        item["message"]: item for item in classified
        if item["category"] in {"BROWSER_DIAGNOSTIC", "FEDCM_BROWSER_DIAGNOSTIC"}
    }
    first_party_console_messages = {
        item["message"] for item in classified
        if item["channel"] == "cdp_console" and item["blocker"]
    }
    for item in classified:
        if (item["channel"] == "playwright_console" and item["message"] in browser_messages
                and item["message"] not in first_party_console_messages):
            source = browser_messages[item["message"]]
            item.update({
                "category": source["category"], "browser_internal": True,
                "blocker": False, "reason": "Playwright duplicate of provenance-confirmed CDP log.",
            })
    unique = []
    seen = set()
    for item in classified:
        identity = (item["category"], item["channel"], item["message"], item["url"],
                    item["line"], item["resource_type"])
        if identity not in seen:
            seen.add(identity)
            unique.append(item)
    return unique


def network_category(url):
    host = (urlsplit(url).hostname or "").lower()
    if host == "formsubmit.co" or host.endswith(".formsubmit.co"):
        return "formsubmit"
    if host == "wa.me" or host.endswith(".whatsapp.com"):
        return "whatsapp"
    if any(host == suffix or host.endswith("." + suffix) for suffix in BLOCKED_HOST_SUFFIXES[1:4]):
        return "analytics"
    return "external"


def should_block(request, origin):
    parsed = urlsplit(request.url)
    origin_host = (urlsplit(origin).hostname or "").lower()
    host = (parsed.hostname or "").lower()
    if any(host == suffix or host.endswith("." + suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        return True
    return request.method != "GET" and host != origin_host


def install_isolation(page, origin, attempts):
    page.add_init_script("""
        window.__lpvGtagEvents = [];
        window.dataLayer = [];
        window.gtag = function () {
          window.__lpvGtagEvents.push(Array.from(arguments));
        };
    """)

    def route_handler(route):
        request = route.request
        if should_block(request, origin):
            attempts.append({
                "category": network_category(request.url),
                "method": request.method,
                "url": sanitized_url(request.url),
            })
            route.abort("blockedbyclient")
        else:
            route.continue_()

    page.route("**/*", route_handler)


def exercise_menu(page):
    toggle = page.locator(".lpv-menu-toggle")
    nav = page.locator("#lpv-primary-nav")
    if toggle.count() != 1 or nav.count() != 1:
        return {"present": False, "opened": False, "escape_closed": False,
                "focus_returned": False}
    toggle.click()
    page.wait_for_timeout(300)
    if toggle.get_attribute("aria-expanded") != "true":
        toggle.click()
        page.wait_for_timeout(150)
    opened = toggle.get_attribute("aria-expanded") == "true"
    first_link = nav.locator("a[href]").first
    if first_link.count():
        first_link.focus()
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    return {
        "present": True,
        "opened": opened,
        "escape_closed": toggle.get_attribute("aria-expanded") == "false",
        "focus_returned": page.evaluate(
            "document.activeElement === document.querySelector('.lpv-menu-toggle')"),
    }


def exercise_form(page, expected_language):
    form = page.locator('form[action^="https://formsubmit.co/"]')
    if form.count() != 1:
        return {"present": False, "request_count": 0}
    context = form.locator("#lpv-form-context")
    language = form.locator("select").first
    context_value = context.input_value()
    language_value = language.input_value()
    required = form.locator("[required]")
    invalid_initially = not form.evaluate("node => node.checkValidity()")
    for index in range(required.count()):
        field = required.nth(index)
        kind = field.get_attribute("type")
        field.fill("runtime@example.test" if kind == "email" else "LPV Runtime Test")
    valid_after_fill = form.evaluate("node => node.checkValidity()")
    page.evaluate("""
        window.__lpvGtagEvents = [];
        window.gtag = function () { window.__lpvGtagEvents.push(Array.from(arguments)); };
    """)
    submit_state = form.evaluate("""node => {
        const button = node.querySelector('button[type="submit"]');
        const before = button.textContent;
        node.requestSubmit();
        const changed = button.disabled || button.textContent !== before;
        node.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        return { changed, events: window.__lpvGtagEvents || [] };
    }""")
    page.wait_for_timeout(200)
    return {
        "present": True,
        "context": context_value,
        "language": language_value,
        "expected_language": expected_language,
        "invalid_initially": invalid_initially,
        "valid_after_fill": valid_after_fill,
        "button_state_changed": submit_state["changed"],
        "analytics_events": submit_state["events"],
    }


def exercise_analytics(page):
    page.evaluate("""
        window.__lpvGtagEvents = [];
        window.gtag = function () { window.__lpvGtagEvents.push(Array.from(arguments)); };
        document.addEventListener('click', event => {
          if (event.target.closest('a')) event.preventDefault();
        }, true);
    """)
    tour = page.locator('a[href*="mosaicos-do-rio"], a[href*="mosaicos-del-rio"], a[href*="mosaics-of-rio"]').first
    whatsapp = page.locator('a[href*="wa.me"]').first
    if tour.count():
        tour.evaluate("node => node.click()")
    if whatsapp.count():
        whatsapp.evaluate("node => node.click()")
    page.wait_for_timeout(100)
    return page.evaluate("window.__lpvGtagEvents || []")


def page_acceptance(browser, url, origin, page_id=None, expected_language=None):
    context = browser.new_context(viewport={"width": 375, "height": 812})
    page = context.new_page()
    page.set_default_timeout(5000)
    attempts, raw_events, page_errors = [], [], []
    cdp_requests = {}
    install_isolation(page, origin, attempts)

    def console_message(message):
        location = message.location.get("url", "")
        if message.type == "error":
            raw_events.append({
                "channel": "playwright_console", "message": message.text,
                "source": "javascript", "level": message.type,
                "url": location, "line": message.location.get("lineNumber"),
                "column": message.location.get("columnNumber"),
                "stack_urls": [],
            })

    def page_error(error):
        text = str(error)
        stack = getattr(error, "stack", "") or ""
        page_errors.append(text)
        stack_urls = re.findall(r"https?://[^\s)]+", stack)
        raw_events.append({
            "channel": "playwright_pageerror", "message": text,
            "source": "javascript", "level": "error", "url": "",
            "stack_urls": stack_urls,
        })

    page.on("console", console_message)
    page.on("pageerror", page_error)

    def request_failed(request):
        if should_block(request, origin):
            return
        raw_events.append({
            "channel": "playwright_request_failed",
            "message": (request.failure or "request failed"),
            "source": "network", "level": "error", "request_url": request.url,
            "resource_type": request.resource_type, "stack_urls": [],
        })

    def response_received(response):
        if response.status >= 400:
            raw_events.append({
                "channel": "playwright_response_failed",
                "message": f"HTTP {response.status}", "source": "network",
                "level": "error", "request_url": response.url,
                "resource_type": response.request.resource_type, "stack_urls": [],
            })

    page.on("requestfailed", request_failed)
    page.on("response", response_received)
    cdp_supported = True
    try:
        cdp = context.new_cdp_session(page)

        def cdp_exception(params):
            details = params.get("exceptionDetails", {})
            exception = details.get("exception", {})
            raw_events.append({
                "channel": "cdp_exception",
                "message": exception.get("description") or details.get("text", ""),
                "source": "javascript", "level": "error",
                "url": details.get("url", ""), "line": details.get("lineNumber"),
                "column": details.get("columnNumber"),
                "stack_urls": cdp_stack_urls(details.get("stackTrace", {})),
            })

        def cdp_console(params):
            raw_events.append({
                "channel": "cdp_console", "message": cdp_argument_text(params.get("args")),
                "source": "javascript", "level": params.get("type", ""), "url": "",
                "stack_urls": cdp_stack_urls(params.get("stackTrace", {})),
            })

        def cdp_log(params):
            entry = params.get("entry", {})
            raw_events.append({
                "channel": "cdp_log", "message": entry.get("text", ""),
                "source": entry.get("source", ""), "level": entry.get("level", ""),
                "url": entry.get("url", ""), "line": entry.get("lineNumber"),
                "column": entry.get("columnNumber"),
                "stack_urls": cdp_stack_urls(entry.get("stackTrace", {})),
                "request_url": cdp_requests.get(entry.get("networkRequestId"), {}).get("url", ""),
                "resource_type": cdp_requests.get(entry.get("networkRequestId"), {}).get("type", "").lower(),
            })

        def cdp_request(params):
            cdp_requests[params.get("requestId")] = {
                "url": params.get("request", {}).get("url", ""),
                "type": params.get("type", ""),
            }

        def cdp_network_failed(params):
            request = cdp_requests.get(params.get("requestId"), {})
            raw_events.append({
                "channel": "cdp_network_failed", "message": params.get("errorText", ""),
                "source": "network", "level": "error",
                "request_url": request.get("url", ""),
                "resource_type": str(params.get("type") or request.get("type", "")).lower(),
                "stack_urls": [],
            })

        def cdp_response(params):
            response = params.get("response", {})
            if response.get("status", 0) >= 400:
                raw_events.append({
                    "channel": "cdp_response_failed",
                    "message": f"HTTP {int(response['status'])}", "source": "network",
                    "level": "error", "request_url": response.get("url", ""),
                    "resource_type": str(params.get("type", "")).lower(), "stack_urls": [],
                })

        cdp.on("Runtime.exceptionThrown", cdp_exception)
        cdp.on("Runtime.consoleAPICalled", cdp_console)
        cdp.on("Log.entryAdded", cdp_log)
        cdp.on("Network.requestWillBeSent", cdp_request)
        cdp.on("Network.loadingFailed", cdp_network_failed)
        cdp.on("Network.responseReceived", cdp_response)
        for method in ("Runtime.enable", "Log.enable", "Network.enable"):
            cdp.send(method)
    except PlaywrightError:
        cdp_supported = False

    result = {"id": page_id, "url": url, "http_status": 0, "checks": {}}
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(500)
        result["http_status"] = response.status if response else 0
        menu = exercise_menu(page)
        internal_links = page.locator(f'a[href^="{origin}"], a[href^="/"]').count()
        analytics = exercise_analytics(page)
        form = exercise_form(page, expected_language) if expected_language else None
        page.wait_for_timeout(200)
        runtime_events = classify_runtime_events(raw_events, origin)
        first_party_exceptions = [item for item in runtime_events
                                  if item["category"] == "FIRST_PARTY_EXCEPTION"]
        first_party_console = [item for item in runtime_events
                               if item["category"] == "FIRST_PARTY_CONSOLE_ERROR"]
        first_party_resources = [item for item in runtime_events
                                 if item["category"] == "FIRST_PARTY_RESOURCE_FAILURE"]
        third_party_diagnostics = [item for item in runtime_events
                                   if item["category"] == "THIRD_PARTY_DIAGNOSTIC"]
        browser_diagnostics = [item for item in runtime_events
                               if item["category"] == "BROWSER_DIAGNOSTIC"]
        fedcm_diagnostics = [item for item in runtime_events
                             if item["category"] == "FEDCM_BROWSER_DIAGNOSTIC"]
        form_attempts = [item for item in attempts if item["category"] == "formsubmit"]
        checks = {
            "http_rendered": result["http_status"] == 200,
            "no_page_errors": not first_party_exceptions,
            "no_lpv_console_errors": not first_party_console,
            "menu_present": menu["present"],
            "menu_opens": menu["opened"],
            "menu_escape_closes": menu["escape_closed"],
            "menu_focus_returned": menu["focus_returned"],
            "internal_links_usable": internal_links > 0,
            "no_relevant_failed_resources": not first_party_resources,
        }
        if form is not None:
            checks.update({
                "form_present": form["present"],
                "form_context_present": bool(form.get("context")),
                "form_language_correct": form.get("language") == expected_language,
                "form_validation": form.get("invalid_initially") and form.get("valid_after_fill"),
                "form_submit_state": form.get("button_state_changed"),
                "form_single_intercepted_submit": len(form_attempts) == 1,
            })
        result.update({
            "checks": checks,
            "menu": menu,
            "form": form,
            "analytics_events": analytics + (form.get("analytics_events", []) if form else []),
            "network_attempts": attempts,
            "console_errors": [{
                "text": item["message"], "source": item["url"] or item["source"],
                "relevant": item["blocker"], "category": item["category"],
            } for item in runtime_events if "CONSOLE" in item["category"]
               or item["channel"] == "playwright_console"],
            "page_errors": page_errors,
            "failed_resources": [item for item in runtime_events
                                 if "RESOURCE_FAILURE" in item["category"]],
            "runtime_events": runtime_events,
            "runtime_summary": {
                "first_party_exceptions": len(first_party_exceptions),
                "first_party_console_errors": len(first_party_console),
                "first_party_critical_resource_failures": len(first_party_resources),
                "third_party_diagnostics": len(third_party_diagnostics),
                "browser_diagnostics": len(browser_diagnostics),
                "fedcm_diagnostics": len(fedcm_diagnostics),
                "cdp_supported": cdp_supported,
            },
        })
    except PlaywrightError as error:
        result["checks"] = {"browser_completed": False}
        result["browser_error"] = str(error)[:1000]
    finally:
        context.close()
    return result


def audit_runtime(origin=ORIGIN, rows=None):
    rows = rows or load_pages()
    executable = browser_executable()
    if not executable:
        raise RuntimeError("A local Chromium browser executable is required.")
    pages = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        try:
            for row in rows:
                pages.append(page_acceptance(
                    browser, origin.rstrip("/") + row["url"], origin.rstrip("/"), row["id"],
                    FORM_PAGE_IDS.get(row["id"]),
                ))
        finally:
            browser.close()
    blockers = []
    functional_failures = []
    technical_checks = {
        "no_page_errors", "no_lpv_console_errors", "no_relevant_failed_resources",
    }
    for page in pages:
        blockers.extend(f"page:{page['id']}:{key}" for key, passed in page["checks"].items()
                        if not passed)
        functional_failures.extend(
            f"page:{page['id']}:{key}" for key, passed in page["checks"].items()
            if not passed and key not in technical_checks)
        serialized_events = json.dumps(page.get("analytics_events", []), ensure_ascii=False)
        if any(value in serialized_events for value in PII_SENTINELS):
            blockers.append(f"page:{page['id']}:analytics_contains_test_pii")
            functional_failures.append(f"page:{page['id']}:analytics_contains_test_pii")
    summaries = [page.get("runtime_summary", {}) for page in pages]
    acceptance = {
        "FIRST_PARTY_EXCEPTIONS": sum(item.get("first_party_exceptions", 0)
                                      for item in summaries),
        "FIRST_PARTY_CONSOLE_ERRORS": sum(item.get("first_party_console_errors", 0)
                                          for item in summaries),
        "FIRST_PARTY_CRITICAL_RESOURCE_FAILURES": sum(
            item.get("first_party_critical_resource_failures", 0) for item in summaries),
        "THIRD_PARTY_DIAGNOSTICS": sum(item.get("third_party_diagnostics", 0)
                                       for item in summaries),
        "BROWSER_DIAGNOSTICS": sum(item.get("browser_diagnostics", 0)
                                   for item in summaries),
        "FEDCM_DIAGNOSTICS": sum(item.get("fedcm_diagnostics", 0)
                                 for item in summaries),
        "FUNCTIONAL_FAILURES": len(functional_failures),
    }
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "origin": origin,
        "browser": Path(executable).name,
        "pages": pages,
        "blockers": blockers,
        "runtime_acceptance": acceptance,
        "functional_failures": functional_failures,
        "status": "APROVADO" if not blockers else "BLOQUEADOR",
        "forms_sent": 0,
        "analytics_sent": 0,
        "network_isolation": "FormSubmit, WhatsApp, analytics and external POST blocked",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default=ORIGIN)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args()
    if args.origin.rstrip("/") == ORIGIN and not args.confirm_production:
        parser.error("Refusing production browser audit without --confirm-production.")
    report = audit_runtime(args.origin.rstrip("/"))
    dump_json(args.output, report)
    print(f"Browser runtime audit: {report['status']}; {len(report['blockers'])} blockers.")
    return 0 if report["status"] == "APROVADO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
