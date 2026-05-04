"""Парсер Dewu/Poizon. Best-effort: Dewu подписывает запросы и геоблочит,
поэтому модуль может вернуть 0 строк — в этом случае используется
scraper.synthetic.

Запуск: python -m scraper.dewu --output data/dewu_raw.csv --pages 1
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

PROXY = os.environ.get("LLM_PROXY_URL")  # SOCKS5/HTTP — пригодится при гео-блоке

UA_DESKTOP = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)


def fetch_url(url: str, headers: dict | None = None, timeout: float = 20.0) -> httpx.Response | None:
    transport = None
    if PROXY:
        transport = httpx.HTTPTransport(proxy=PROXY)
    try:
        with httpx.Client(transport=transport, timeout=timeout, follow_redirects=True) as cli:
            return cli.get(url, headers=headers or {"User-Agent": UA_DESKTOP})
    except Exception as exc:
        print(f"[fetch error] {url}: {exc}", file=sys.stderr)
        return None


def try_dewu_search(query: str) -> list[dict]:
    """Попытка через web-каталог dewu.com."""
    url = f"https://www.dewu.com/search?title={query}"
    resp = fetch_url(url)
    if not resp or resp.status_code != 200:
        print(f"[dewu] {url} -> {resp.status_code if resp else 'no resp'}", file=sys.stderr)
        return []
    text = resp.text
    m = re.search(r"<script id=\"__NEXT_DATA__\"[^>]*>(.+?)</script>", text, re.S)
    if not m:
        print("[dewu] __NEXT_DATA__ не найден — вероятно, антибот/капча", file=sys.stderr)
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    items = data.get("props", {}).get("pageProps", {}).get("data", {}).get("list", [])
    return items if isinstance(items, list) else []


def normalize_item(it: dict) -> dict:
    title = it.get("title") or it.get("productName") or ""
    desc = it.get("description") or it.get("subtitle") or ""
    price_raw = it.get("price") or it.get("salePrice") or ""
    if isinstance(price_raw, (int, float)):
        price_raw = f"¥{int(price_raw)}"
    spu = it.get("spuId") or it.get("id") or ""
    url = f"https://www.dewu.com/product/{spu}" if spu else ""
    return {
        "raw_title": title,
        "raw_description": desc,
        "raw_price": str(price_raw),
        "source_url": url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Best-effort парсер Dewu (Poizon).")
    parser.add_argument("--output", required=True)
    parser.add_argument("--queries", nargs="+", default=["air jordan", "yeezy", "supreme"])
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    rows: list[dict] = []
    for q in args.queries:
        print(f"[dewu] querying {q!r}…")
        items = try_dewu_search(q)
        print(f"[dewu]   got {len(items)} items")
        for it in items:
            rows.append(normalize_item(it))
            if len(rows) >= args.limit:
                break
        time.sleep(1.0)
        if len(rows) >= args.limit:
            break

    if not rows:
        print(
            "[dewu] не удалось получить ни одной карточки. Используй scraper.synthetic.",
            file=sys.stderr,
        )
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "raw_title", "raw_description", "raw_price", "source_url"])
        writer.writeheader()
        for i, r in enumerate(rows, 1):
            writer.writerow({"id": i, **r})

    print(f"[dewu] wrote {len(rows)} rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
