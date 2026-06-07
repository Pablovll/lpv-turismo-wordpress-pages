#!/usr/bin/env python3
from pathlib import Path
import json
import requests
from bs4 import BeautifulSoup

SITE = "https://www.lpvturismo.com"
OUT = Path("pages/raw")
OUT.mkdir(parents=True, exist_ok=True)

url = f"{SITE}/wp-json/wp/v2/pages?per_page=100&status=publish&_fields=id,slug,link,title,content"
pages = requests.get(url, timeout=30).json()
index = []

for p in pages:
    title = BeautifulSoup(p["title"]["rendered"], "html.parser").get_text()
    fname = f'{p["id"]}-{p["slug"]}.html'
    html = str(BeautifulSoup(p["content"]["rendered"], "html.parser"))
    (OUT / fname).write_text(html, encoding="utf-8")
    index.append({"id": p["id"], "title": title, "slug": p["slug"], "url": p["link"], "file": str(OUT / fname)})

(OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Exportadas {len(index)} páginas para {OUT}")
