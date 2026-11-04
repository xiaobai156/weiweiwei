"""单站渲染探针：确认指定页面当前是否已发布 305 期（只读）。"""
from __future__ import annotations

import re
import sys
from collections import Counter

from playwright.sync_api import sync_playwright

URL = "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/241106.html"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        ctx = browser.new_context(ignore_https_errors=True, user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            html = page.content()
            text = page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            print("渲染失败:", type(exc).__name__, exc)
            browser.close()
            return 1
        browser.close()

    print("html bytes", len(html), "text chars", len(text))
    periods = re.findall(r"(?<!\d)(2\d\d)\s*期", text)
    print("正文期数分布:", Counter(periods).most_common(15))
    for kw in ("305", "304", "306"):
        print(f"'{kw}' in text:", text.count(kw))
    print("---- 正文前 600 字 ----")
    print(text[:600])
    open("render_visible.txt", "w", encoding="utf-8").write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
