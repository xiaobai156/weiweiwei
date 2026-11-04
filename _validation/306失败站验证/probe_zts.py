"""张天师 306 期行文本探针（只读）。"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

URL = "https://wwlhc.com/thread-87037-1-1.html"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        ctx = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = ctx.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            html = page.content()
            text = page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            print("渲染失败:", type(exc).__name__, exc)
            browser.close()
            return 1
        browser.close()

    open("zts_visible.txt", "w", encoding="utf-8").write(text)
    open("zts_page.html", "w", encoding="utf-8").write(html)
    print("html", len(html), "text", len(text))
    for keyword in ("305期", "306期"):
        idx = text.find(keyword)
        print(f"--- {keyword} first at {idx} ---")
        if idx >= 0:
            print(repr(text[idx - 40 : idx + 200]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
