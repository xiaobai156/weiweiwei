# -*- coding: utf-8 -*-
"""317：验证「body inner_text 丢数据行」是否由 content-visibility:auto 引起（只读）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright  # noqa: E402

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

TARGETS = [
    ("刘半仙", "https://smnwgqcm.vkk2k-rpbnk-qtocig.xyz:16677/", "绝杀一尾"),
    ("飞龙在天", "https://anhomo.n03wh-m2skn-wssphn.xyz/", "绝杀一尾"),
    ("跑马图", "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/", "绝杀二尾"),
]

ROW_RE = re.compile(r"3[01]\d期\s*.{0,16}")


def count_rows(text: str, key: str) -> tuple[int, list[str]]:
    hits = [m.group(0) + key for m in ROW_RE.finditer(text) if key in text[m.start() : m.start() + 60]]
    return len(hits), hits[:3]


def main() -> None:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=True,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for name, url, key in TARGETS:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            base = page.locator("body").inner_text()
            n0, _ = count_rows(base, key)
            print(f"=== {name} 初次 body 长度={len(base)} 数据行={n0}", flush=True)
            page.add_style_tag(content="*{content-visibility:visible!important}")
            page.wait_for_timeout(500)
            forced = page.locator("body").inner_text()
            n1, s1 = count_rows(forced, key)
            print(f"   强制可见后 长度={len(forced)} 数据行={n1} 示例={s1}", flush=True)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            scrolled = page.locator("body").inner_text()
            n2, _ = count_rows(scrolled, key)
            print(f"   滚到底后 长度={len(scrolled)} 数据行={n2}", flush=True)
        ctx.close()


if __name__ == "__main__":
    main()
