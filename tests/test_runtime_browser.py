import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.audit_runtime_browser import (browser_executable, classify_runtime_event,
                                           classify_runtime_events, page_acceptance)


ROOT = Path(__file__).resolve().parents[1]
APPROVED_FORM = (ROOT / "publication/stage-6/html/pt/19-quero-montar-meu-roteiro.html").read_text(
    encoding="utf-8")


class RuntimeHandler(BaseHTTPRequestHandler):
    document = ""

    def log_message(self, _format, *_args):
        pass

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/missing-first-party.js":
            self.send_response(404)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            return
        payload = self.document.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class BrowserRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = browser_executable()
        if not executable:
            raise AssertionError("Critical browser tests require local Chromium.")
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=executable)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def test_menu_form_double_submit_network_isolation_and_analytics_stub(self):
        RuntimeHandler.document = (
            '<!doctype html><html lang="pt-BR"><body><main>'
            + '<a href="/passeios/mosaicos-do-rio/">Tour fixture</a>'
            + APPROVED_FORM.replace("https://lpvturismo.com/", self.origin + "/")
            + '</main></body></html>')
        report = page_acceptance(self.browser, self.origin + "/", self.origin, 19, "Português")
        for check in ("http_rendered", "no_page_errors", "no_lpv_console_errors",
                      "menu_present", "menu_opens",
                      "menu_escape_closes", "menu_focus_returned", "internal_links_usable",
                      "form_present", "form_context_present", "form_language_correct",
                      "form_validation", "form_submit_state", "form_single_intercepted_submit"):
            self.assertTrue(report["checks"][check], (check, report))
        self.assertEqual(sum(item["category"] == "formsubmit"
                             for item in report["network_attempts"]), 1)
        event_names = [event[1] for event in report["analytics_events"]
                       if len(event) > 1 and event[0] == "event"]
        self.assertIn("lpv_tour_open", event_names)
        self.assertIn("lpv_whatsapp_click", event_names)
        self.assertIn("lpv_proposal_request_submit", event_names)

    def test_runtime_exception_is_a_real_blocker(self):
        RuntimeHandler.document = """<!doctype html><html><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script>setTimeout(() => { throw new Error('LPV fixture failure'); }, 10)</script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/broken", self.origin, 7)
        self.assertFalse(report["checks"]["no_page_errors"])
        self.assertTrue(any("LPV fixture failure" in item for item in report["page_errors"]))

    def test_observed_litespeed_configuration_error_is_a_real_blocker(self):
        RuntimeHandler.document = """<!doctype html><html><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script>console.error('Error: Configuration data not found');</script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/litespeed-broken", self.origin, 7)
        self.assertFalse(report["checks"]["no_lpv_console_errors"])
        self.assertTrue(any("Configuration data not found" in item["text"]
                            for item in report["console_errors"]))

    def test_untransformed_first_party_script_runs_without_configuration_error(self):
        RuntimeHandler.document = """<!doctype html><html lang="pt-BR"><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script>
        window.lpvFixtureConfiguration = { ready: true };
        if (!window.lpvFixtureConfiguration.ready) {
          throw new Error('Configuration data not found');
        }
        </script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/untransformed", self.origin, 7)
        self.assertTrue(report["checks"]["no_page_errors"], report)
        self.assertTrue(report["checks"]["no_lpv_console_errors"], report)

    def test_same_origin_throw_with_fedcm_text_is_still_blocking(self):
        RuntimeHandler.document = """<!doctype html><html><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script>throw new Error("Provider's accounts list is empty.")</script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/throw-fedcm-text", self.origin, 7)
        self.assertFalse(report["checks"]["no_page_errors"])
        self.assertGreater(report["runtime_summary"]["first_party_exceptions"], 0)

    def test_same_origin_console_error_with_fedcm_text_is_still_blocking(self):
        RuntimeHandler.document = """<!doctype html><html><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script>console.error("Provider's accounts list is empty.")</script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/console-fedcm-text", self.origin, 7)
        self.assertFalse(report["checks"]["no_lpv_console_errors"])
        self.assertGreater(report["runtime_summary"]["first_party_console_errors"], 0)

    def test_reference_error_in_menu_handler_is_blocking(self):
        RuntimeHandler.document = """<!doctype html><html><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script>document.querySelector('.lpv-menu-toggle').addEventListener('click', () => missingMenuHandler());</script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/broken-menu", self.origin, 7)
        self.assertFalse(report["checks"]["no_page_errors"])

    def test_error_in_form_handler_is_blocking(self):
        RuntimeHandler.document = (
            '<!doctype html><html lang="pt-BR"><body><main><a href="/">Home</a>'
            + APPROVED_FORM.replace("https://lpvturismo.com/", self.origin + "/")
            + "<script>document.querySelector('form').addEventListener('submit', () => missingFormHandler());</script>"
            + "</main></body></html>")
        report = page_acceptance(self.browser, self.origin + "/broken-form", self.origin,
                                 19, "Português")
        self.assertFalse(report["checks"]["no_page_errors"])

    def test_first_party_javascript_404_is_blocking(self):
        RuntimeHandler.document = """<!doctype html><html><body>
        <header class="topbar"><button class="lpv-menu-toggle" aria-expanded="false"></button>
        <nav id="lpv-primary-nav"><a href="/">Home</a></nav></header>
        <script src="/missing-first-party.js"></script>
        </body></html>"""
        report = page_acceptance(self.browser, self.origin + "/missing-script", self.origin, 7)
        self.assertFalse(report["checks"]["no_relevant_failed_resources"])
        self.assertGreater(report["runtime_summary"]["first_party_critical_resource_failures"], 0)

    def test_synthetic_exception_stack_on_lpv_origin_is_blocking(self):
        event = classify_runtime_event({
            "channel": "cdp_exception", "message": "ReferenceError", "level": "error",
            "source": "javascript", "stack_urls": ["https://lpvturismo.com/app.js"],
        }, "https://lpvturismo.com")
        self.assertTrue(event["blocker"])
        self.assertEqual(event["category"], "FIRST_PARTY_EXCEPTION")

    def test_browser_and_third_party_provenance_are_non_blocking(self):
        fixtures = [
            ({"channel": "cdp_log", "message": "render warning", "source": "rendering",
              "level": "warning", "url": "https://lpvturismo.com/", "stack_urls": []},
             "BROWSER_DIAGNOSTIC"),
            ({"channel": "cdp_log", "message": "deprecated feature", "source": "deprecation",
              "level": "warning", "stack_urls": []}, "BROWSER_DIAGNOSTIC"),
            ({"channel": "cdp_console", "message": "vendor warning", "source": "javascript",
              "level": "error", "stack_urls": ["https://vendor.example/sdk.js"]},
             "THIRD_PARTY_DIAGNOSTIC"),
        ]
        for raw, category in fixtures:
            with self.subTest(category=category):
                event = classify_runtime_event(raw, "https://lpvturismo.com")
                self.assertFalse(event["blocker"])
                self.assertEqual(event["category"], category)

    def test_fedcm_requires_browser_log_provenance_and_downgrades_playwright_duplicate(self):
        text = "Provider's accounts list is empty."
        events = classify_runtime_events([
            {"channel": "playwright_console", "message": text, "source": "javascript",
             "level": "error", "url": "https://lpvturismo.com/", "stack_urls": []},
            {"channel": "cdp_log", "message": text, "source": "other", "level": "error",
             "url": "https://lpvturismo.com/", "stack_urls": []},
        ], "https://lpvturismo.com")
        self.assertTrue(all(not event["blocker"] for event in events))
        self.assertTrue(all(event["category"] == "FEDCM_BROWSER_DIAGNOSTIC" for event in events))


if __name__ == "__main__":
    unittest.main()
