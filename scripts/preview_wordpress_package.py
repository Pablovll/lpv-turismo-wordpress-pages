#!/usr/bin/env python3
"""Local-only preview of the prepared fragments, not a WordPress emulator."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from build_wordpress_package import ROOT, hreflang_html, load_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    _, records = load_records()
    routes = {record["url"]: record for record in records}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/politica-de-privacidade/":
                self.send_response(302)
                self.send_header("Location", "https://lpvturismo.com/politica-de-privacidade/")
                self.end_headers()
                return
            if path == "/css/lpv-style.css":
                content = (ROOT / "css/lpv-style.css").read_bytes()
                mime = "text/css; charset=utf-8"
            elif path in routes:
                record = routes[path]
                fragment = (ROOT / record["source"]).read_text(encoding="utf-8")
                content = (f'<!doctype html><html lang="{record["lang"]}"><head>'
                           '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                           f'<title>{escape(record["title"])}</title>'
                           '<link rel="stylesheet" href="/css/lpv-style.css">'
                           f'{hreflang_html(record)}</head>'
                           f'<body class="wp-singular page page-id-{record["id"]}">'
                           '<div class="wp-site-blocks"><main id="wp--skip-link--target">'
                           f'<div class="entry-content wp-block-post-content">{fragment}</div></main></div>'
                           '</body></html>').encode("utf-8")
                mime = "text/html; charset=utf-8"
            else:
                self.send_error(404, "Not part of this local package")
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Security-Policy", "form-action 'none'; connect-src 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Local preview: http://127.0.0.1:{args.port}/ (form submission blocked)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
