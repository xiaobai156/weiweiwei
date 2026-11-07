# -*- coding: utf-8 -*-
"""310 期 奉陪到底 渲染探针：确认页面是否已发布 310 期（只读）。"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://jkofyya.6sf58-wbz5a-thviwx.work:29477/article/admin/6a13ec06741e3e91a04e597f?url=jbp"
OUT = Path(__file__).with_name("render_fpd.txt")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        ctx = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            text = page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            print("渲染失败:", type(exc).__name__, exc)
            browser.close()
            return 1
        browser.close()

    OUT.write_text(text, encoding="utf-8")
    print("html bytes", len(html), "text chars", len(text), "->", OUT)
    periods = re.findall(r"(?<!\d)(\d{2,4})\s*期", text)
    print("期数分布:", Counter(periods).most_common(15))
    for kw in ("310", "309", "308"):
        print(f"'{kw}' 出现:", text.count(kw))
    idx = text.find("309")
    print("---- 309 附近 400 字 ----")
    print(text[max(0, idx - 200): idx + 400] if idx >= 0 else "未找到 309")
    return 0


if __name__ == "__main__":
    sys.exit(main())
