#!/usr/bin/env python3
from pathlib import Path
from bs4 import BeautifulSoup
import requests

SITE = "https://www.lpvturismo.com"
folders = [Path("pages/pt"), Path("pages/es"), Path("pages/en"), Path("pages/raw")]
problems = []

for folder in folders:
    for file in folder.glob("*.html"):
        soup = BeautifulSoup(file.read_text(encoding="utf-8"), "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("#", "mailto:", "tel:", "https://wa.me/")):
                continue
            url = SITE + href if href.startswith("/") else href if href.startswith(SITE) else None
            if not url:
                continue
            try:
                r = requests.get(url, timeout=10)
                if r.status_code >= 400:
                    problems.append((str(file), href, r.status_code))
            except Exception as e:
                problems.append((str(file), href, str(e)))

if not problems:
    print("Nenhum link interno quebrado encontrado.")
else:
    for file, href, status in problems:
        print(f"{file}: {href} -> {status}")
