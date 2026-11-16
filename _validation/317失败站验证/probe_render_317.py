# -*- coding: utf-8 -*-
"""317：三站“没有找到317期”渲染取证（只读，保存页面文本，不写正式输出）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright  # noqa: E402

from shawei.fetch.browser import browser_profile_dir  # noqa: E402

TARGETS = [
    ("刘半仙", "https://smnwgqcm.vkk2k-rpbnk-qtocig.xyz:16677/"),
    ("飞龙在天", "https://anhomo.n03wh-m2skn-wssphn.xyz/"),
    ("跑马图", "https://sxapnxtw.w9lkt-9vch6-idlact.work:17477/"),
]
OUT = Path(__file__).parent


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
        for name, url in TARGETS:
            tag = f"317_{name}"
            try:
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                html = page.content()
                text = page.inner_text("body")
            except Exception as exc:  # noqa: BLE001 - 取证需要原始错误
                print(f"[{name}] 渲染失败 {type(exc).__name__}: {exc}", flush=True)
                continue
            (OUT / f"render_{tag}.html").write_text(html, encoding="utf-8")
            (OUT / f"render_{tag}.txt").write_text(text, encoding="utf-8")
            periods = sorted({int(x) for x in re.findall(r"(3[0-2]\d)\s*期", text)})
            print(f"[{name}] url={url} 文本长度={len(text)} 出现期号={periods}", flush=True)
            hits = [ln.strip() for ln in text.splitlines() if "317" in ln]
            print(f"   含317的行({len(hits)}):", flush=True)
            for ln in hits[:12]:
                print("     ", ln[:160], flush=True)
        ctx.close()


if __name__ == "__main__":
    main()
