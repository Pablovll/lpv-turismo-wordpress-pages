#!/usr/bin/env python3
"""Read-only public WordPress checks. Never authenticates or submits forms."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def inspect_page(url):
    record = {"requested_url": url}
    try:
        try:
            response = urlopen(url, timeout=35)
        except HTTPError as error:
            response = error
        with response:
            content = response.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        record.update({
            "http_status": response.status,
            "final_url": response.url,
            "lang": soup.html.get("lang") if soup.html else None,
            "title": soup.title.get_text(strip=True) if soup.title else None,
            "canonical": [link.get("href") for link in soup.select('link[rel="canonical"]')],
            "hreflang": [{"lang": link.get("hreflang"), "url": link.get("href")}
                         for link in soup.select('link[rel="alternate"][hreflang]')],
            "native_post_titles": len(soup.select(".wp-block-post-title")),
            "native_headers": len(soup.select("header.wp-block-template-part")),
            "native_footers": len(soup.select("footer.wp-block-template-part")),
            "custom_headers": len(soup.select("header.topbar")),
            "custom_footers": len(soup.select("footer.lpv-site-footer")),
            "h1_count": len(soup.select("h1")),
            "main_count": len(soup.select("main")),
            "aioseo_marker": "aioseo" in content.lower(),
            "yoast_marker": "yoast" in content.lower(),
        })
    except (URLError, TimeoutError, UnicodeError) as error:
        record["error"] = str(error)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    page_map = json.loads((ROOT / "docs/page-map.json").read_text(encoding="utf-8"))
    urls = [page_map["site"] + page["url"]
            for pages in page_map["pages"].values() for page in pages.values()]
    urls.append("https://lpvturismo.com/politica-de-privacidade/")
    records = [inspect_page(url) for url in urls]
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "Unauthenticated HTTP GET only. Status 200 does not prove WP publish status.",
        "pages": records,
    }
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
