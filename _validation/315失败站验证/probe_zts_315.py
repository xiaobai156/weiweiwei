# -*- coding: utf-8 -*-
"""315 期张天师页面取证：用项目持久化 profile 渲染，保存正文并打印候选行。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

URL = "https://wwlhc.com/thread-87037-1-1.html"


def main() -> None:
    from playwright.sync_api import sync_playwright

    out_dir = Path(__file__).parent
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            browser_profile_dir(),
            headless=True,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            html = page.content()
            text = page.inner_text("body")
        finally:
            ctx.close()
    (out_dir / "render_zts_315.html").write_text(html, encoding="utf-8")
    (out_dir / "render_zts_315.txt").write_text(text, encoding="utf-8")
    print("HTML 长度", len(html), "正文长度", len(text))
    print("logged_in hints:", "退出" in html, "登录" in html)
    for line in text.splitlines():
        s = line.strip()
        if re.search(r"31[3-5]\s*期", s):
            print(repr(s))


if __name__ == "__main__":
    main()
